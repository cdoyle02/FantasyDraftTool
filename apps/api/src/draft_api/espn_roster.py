"""Fetch ESPN league rosters and free agents for Workbook overlay."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from draft_api.espn_available_dst import PRO_TEAM_IDS, default_http_json
from draft_api.workbook.identity import normalize_team

ESPN_READ_HOST = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"

POSITION_IDS: dict[int, str] = {
    1: "QB",
    2: "RB",
    3: "WR",
    4: "TE",
    5: "K",
    16: "DST",
}

LINEUP_SLOT_IDS: dict[int, str] = {
    0: "QB",
    2: "RB",
    3: "RB/WR",
    4: "WR",
    5: "WR/TE",
    6: "TE",
    7: "OP",
    16: "DST",
    17: "K",
    20: "BENCH",
    21: "IR",
    23: "FLEX",
}

HttpJsonGetter = Callable[[str, dict[str, str]], Any]


class EspnRosterError(RuntimeError):
    """Raised when ESPN roster/FA fetch fails."""


@dataclass(frozen=True, slots=True)
class EspnRosterPlayer:
    player_id: int
    full_name: str
    nfl_team: str
    roster_slot: str
    lineup_slot: str | None
    injury_status: str | None
    espn_team_id: int | None
    availability: str


def _nfl_team(pro_team_id: Any) -> str:
    if pro_team_id is None:
        return "UNK"
    try:
        team = PRO_TEAM_IDS.get(int(pro_team_id), "UNK")
    except (TypeError, ValueError):
        return "UNK"
    return normalize_team(team)


def _parse_roster_entry(
    entry: dict[str, Any],
    *,
    espn_team_id: int,
) -> EspnRosterPlayer | None:
    pool = entry.get("playerPoolEntry") if isinstance(entry.get("playerPoolEntry"), dict) else {}
    player = pool.get("player") if isinstance(pool.get("player"), dict) else {}
    if not player:
        return None
    raw_player_id = entry.get("playerId")
    if raw_player_id is None:
        raw_player_id = player.get("id")
    try:
        player_id = int(raw_player_id)
    except (TypeError, ValueError):
        return None
    position_id = int(player.get("defaultPositionId") or 0)
    raw_slot = entry.get("lineupSlotId")
    slot_id = int(raw_slot) if raw_slot is not None else -1
    injury = player.get("injuryStatus")
    return EspnRosterPlayer(
        player_id=player_id,
        full_name=str(player.get("fullName") or "Unknown"),
        nfl_team=_nfl_team(player.get("proTeamId")),
        roster_slot=POSITION_IDS.get(position_id, str(position_id)),
        lineup_slot=LINEUP_SLOT_IDS.get(slot_id),
        injury_status=str(injury) if injury else None,
        espn_team_id=espn_team_id,
        availability="ONTEAM",
    )


def parse_league_roster(payload: dict[str, Any]) -> list[EspnRosterPlayer]:
    """Parse ``mTeam`` / ``mRoster`` league payload into flat player rows."""
    teams = payload.get("teams")
    if not isinstance(teams, list):
        raise EspnRosterError("ESPN returned an unexpected payload")
    players: list[EspnRosterPlayer] = []
    for team in teams:
        if not isinstance(team, dict):
            continue
        try:
            espn_team_id = int(team.get("id") or 0)
        except (TypeError, ValueError):
            continue
        roster = team.get("roster") if isinstance(team.get("roster"), dict) else {}
        for entry in roster.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            parsed = _parse_roster_entry(entry, espn_team_id=espn_team_id)
            if parsed is not None:
                players.append(parsed)
    return players


def _member_index(members: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for member in members:
        if not isinstance(member, dict):
            continue
        member_id = str(member.get("id") or "")
        if not member_id:
            continue
        indexed[member_id] = {
            "display_name": str(member.get("displayName") or ""),
            "first_name": str(member.get("firstName") or ""),
            "last_name": str(member.get("lastName") or ""),
        }
    return indexed


def _owner_matches(owner: dict[str, str], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return False
    fields = (
        owner.get("display_name") or "",
        owner.get("first_name") or "",
        owner.get("last_name") or "",
        " ".join(
            part
            for part in (owner.get("first_name"), owner.get("last_name"))
            if part
        ),
    )
    return any(needle in field.lower() for field in fields if field)


def resolve_owner_team_id(payload: dict[str, Any], *, owner: str) -> int | None:
    """Resolve ESPN fantasy team id from owner name query against ``mTeam`` payload."""
    if not owner.strip():
        return None
    members = _member_index(payload.get("members") or [])
    for team in payload.get("teams") or []:
        if not isinstance(team, dict):
            continue
        primary = str(team.get("primaryOwner") or "")
        owner_info = members.get(primary, {})
        if _owner_matches(owner_info, owner):
            try:
                return int(team.get("id"))
            except (TypeError, ValueError):
                return None
        for owner_id in team.get("owners") or []:
            info = members.get(str(owner_id), {})
            if _owner_matches(info, owner):
                try:
                    return int(team.get("id"))
                except (TypeError, ValueError):
                    return None
    return None


def _league_url(*, league_id: str, season: int, views: list[str]) -> str:
    query = urllib.parse.urlencode([("view", view) for view in views])
    return f"{ESPN_READ_HOST}/seasons/{season}/segments/0/leagues/{league_id}?{query}"


def _auth_headers(
    *,
    espn_s2: str,
    swid: str,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        "User-Agent": "FantasyDraftTool-workbook-roster/1.0",
        "Accept": "application/json",
        "Cookie": f"espn_s2={espn_s2}; SWID={swid}",
    }
    if extra:
        headers.update(extra)
    return headers


def fetch_league_roster(
    *,
    league_id: str,
    season: int,
    espn_s2: str,
    swid: str,
    http_json: HttpJsonGetter | None = None,
) -> list[EspnRosterPlayer]:
    """Return all rostered players for a league (``mTeam`` + ``mRoster``)."""
    url = _league_url(league_id=league_id, season=season, views=["mTeam", "mRoster"])
    getter = http_json or default_http_json
    try:
        payload = getter(url, _auth_headers(espn_s2=espn_s2, swid=swid))
    except EspnRosterError:
        raise
    except Exception as exc:
        if isinstance(exc, urllib.error.HTTPError):
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise EspnRosterError(f"ESPN HTTP {exc.code}: {body}") from exc
        raise EspnRosterError(f"ESPN request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise EspnRosterError("ESPN returned an unexpected payload")
    return parse_league_roster(payload)


def _parse_free_agent_entry(entry: dict[str, Any]) -> EspnRosterPlayer | None:
    player = entry.get("player") if isinstance(entry.get("player"), dict) else {}
    if not player:
        return None
    try:
        player_id = int(player.get("id"))
    except (TypeError, ValueError):
        return None
    position_id = int(player.get("defaultPositionId") or 0)
    status = str(entry.get("status") or "FREEAGENT")
    injury = player.get("injuryStatus")
    return EspnRosterPlayer(
        player_id=player_id,
        full_name=str(player.get("fullName") or "Unknown"),
        nfl_team=_nfl_team(player.get("proTeamId")),
        roster_slot=POSITION_IDS.get(position_id, str(position_id)),
        lineup_slot=None,
        injury_status=str(injury) if injury else None,
        espn_team_id=None,
        availability=status,
    )


def fetch_league_free_agents(
    *,
    league_id: str,
    season: int,
    espn_s2: str,
    swid: str,
    limit: int = 50,
    statuses: list[str] | None = None,
    http_json: HttpJsonGetter | None = None,
) -> list[EspnRosterPlayer]:
    """Return free-agent and waiver players (paged ``kona_player_info``)."""
    status_list = list(statuses or ["FREEAGENT", "WAIVERS"])
    fantasy_filter = {
        "players": {
            "filterStatus": {"value": status_list},
            "limit": limit,
            "offset": 0,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }
    query = urllib.parse.urlencode([("view", "kona_player_info")])
    url = f"{ESPN_READ_HOST}/seasons/{season}/segments/0/leagues/{league_id}?{query}"
    headers = _auth_headers(
        espn_s2=espn_s2,
        swid=swid,
        extra={"X-Fantasy-Filter": json.dumps(fantasy_filter)},
    )
    getter = http_json or default_http_json
    payload = getter(url, headers)
    if not isinstance(payload, dict):
        raise EspnRosterError("ESPN returned an unexpected payload")
    players: list[EspnRosterPlayer] = []
    for entry in payload.get("players") or []:
        if not isinstance(entry, dict):
            continue
        status = entry.get("status") or ""
        if status not in status_list:
            continue
        parsed = _parse_free_agent_entry(entry)
        if parsed is not None:
            players.append(parsed)
    return players
