"""Compact ESPN roster rows shared by the export script and the MCP tool.

The export script still writes only the cookie owner's teams. The MCP tool
uses the same player shape for every team in a league.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .client import EspnError
from .reference import LINEUP_SLOT_IDS, POSITION_IDS, PRO_TEAM_IDS

# Starter slots first, then bench/IR, then any unknown ESPN slot ids.
SLOT_SORT = {
    "QB": 0,
    "RB": 1,
    "RB/WR": 2,
    "WR": 3,
    "WR/TE": 4,
    "TE": 5,
    "FLEX": 6,
    "OP": 7,
    "DST": 8,
    "K": 9,
    "BENCH": 10,
    "IR": 11,
}


def round_stat(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def record_line(team: dict[str, Any]) -> str:
    overall = (team.get("record") or {}).get("overall") or {}
    wins = int(overall.get("wins") or 0)
    losses = int(overall.get("losses") or 0)
    ties = int(overall.get("ties") or 0)
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def bye_map(season_meta: dict[str, Any]) -> dict[int, int]:
    teams = ((season_meta.get("settings") or {}).get("proTeams") or [])
    return {
        int(team["id"]): int(team["byeWeek"])
        for team in teams
        if "id" in team and "byeWeek" in team
    }


def normalize_player(entry: dict[str, Any], *, bye_weeks: dict[int, int]) -> dict[str, Any]:
    pool = entry.get("playerPoolEntry") or {}
    player = pool.get("player") or {}
    ownership = player.get("ownership") or {}
    position_id = int(player.get("defaultPositionId") or 0)
    pro_team_id = int(player.get("proTeamId") or 0)
    raw_slot = entry.get("lineupSlotId")
    slot_id = int(raw_slot) if raw_slot is not None else -1
    raw_player_id = entry.get("playerId")
    if raw_player_id is None:
        raw_player_id = player.get("id") or 0
    return {
        "espn_player_id": int(raw_player_id),
        "name": str(player.get("fullName") or ""),
        "position": POSITION_IDS.get(position_id, str(position_id)),
        "nfl_team": PRO_TEAM_IDS.get(pro_team_id, str(pro_team_id)),
        "bye_week": bye_weeks.get(pro_team_id),
        "lineup_slot": LINEUP_SLOT_IDS.get(slot_id, str(slot_id)),
        "lineup_slot_id": slot_id,
        "injury_status": str(player.get("injuryStatus") or entry.get("injuryStatus") or ""),
        "injured": bool(player.get("injured")),
        "acquisition_type": str(entry.get("acquisitionType") or ""),
        "percent_owned": round_stat(ownership.get("percentOwned")),
        "percent_started": round_stat(ownership.get("percentStarted")),
        "fantasy_points": round_stat(pool.get("appliedStatTotal")),
    }


def sort_players(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        players,
        key=lambda player: (
            SLOT_SORT.get(str(player["lineup_slot"]), 99),
            str(player["position"]),
            str(player["name"]),
        ),
    )


def member_index(members: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for member in members:
        member_id = str(member.get("id") or "")
        if not member_id:
            continue
        indexed[member_id] = {
            "id": member_id,
            "display_name": str(member.get("displayName") or ""),
            "first_name": str(member.get("firstName") or ""),
            "last_name": str(member.get("lastName") or ""),
        }
    return indexed


def team_owner(team: dict[str, Any], members: dict[str, dict[str, str]]) -> dict[str, str]:
    primary = str(team.get("primaryOwner") or "")
    if primary in members:
        return members[primary]
    for owner in team.get("owners") or []:
        owner_id = str(owner)
        if owner_id in members:
            return members[owner_id]
    return {"id": primary, "display_name": "", "first_name": "", "last_name": ""}


def owner_name(owner: dict[str, str]) -> str:
    parts = (owner.get("first_name"), owner.get("last_name"))
    return " ".join(part for part in parts if part).strip()


def owner_matches(owner: dict[str, str], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    fields = [
        owner.get("display_name") or "",
        owner.get("first_name") or "",
        owner.get("last_name") or "",
        owner_name(owner),
    ]
    return any(needle in field.lower() for field in fields if field)


def team_owned_by(team: dict[str, Any], swid: str) -> bool:
    if str(team.get("primaryOwner") or "") == swid:
        return True
    return swid in {str(owner) for owner in (team.get("owners") or [])}


def configured_leagues() -> list[dict[str, str]]:
    """Leagues packaged with the API, or the repo JSON when the API isn't installed."""
    try:
        from draft_api.espn_leagues import load_espn_leagues
    except ImportError:
        path = (
            Path(__file__).resolve().parents[4]
            / "apps/api/src/draft_api/data/espn_leagues.json"
        )
        if not path.is_file():
            raise EspnError("ESPN league directory is not available in this install.") from None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [
            {"id": str(item["id"]), "name": str(item["name"])}
            for item in payload
            if item.get("id") and item.get("name")
        ]
    return load_espn_leagues()


def select_leagues(leagues: list[dict[str, str]], league: str | None) -> list[dict[str, str]]:
    if league is None or not league.strip():
        return list(leagues)
    text = league.strip()
    by_id = [item for item in leagues if item["id"] == text]
    if by_id:
        return by_id
    needle = text.lower()
    by_name = [item for item in leagues if needle in item["name"].lower()]
    if not by_name:
        known = ", ".join(f"{item['name']} ({item['id']})" for item in leagues)
        raise EspnError(f"Unknown league {text!r}. Known leagues: {known}")
    return by_name


def resolve_roster_query(
    *,
    profile_name: str | None,
    league: str | None,
    owner: str | None,
    mine: bool | None,
) -> tuple[bool, bool]:
    """Return (restrict_to_cookie_owner, include_player_rows).

    Katie's hosted login defaults to her own team when the caller names neither
    a league nor an owner. A full league still needs an explicit league or owner
    so a four-league dump does not land in the chat by accident.
    """
    restrict_to_owner = bool(mine)
    if mine is None and not owner and not league and profile_name == "katie":
        restrict_to_owner = True
    include_players = bool(league or owner or restrict_to_owner)
    return restrict_to_owner, include_players


def normalize_teams(
    payload: dict[str, Any],
    *,
    league_id: str,
    league_name: str,
    bye_weeks: dict[int, int],
    owner_swid: str | None,
    owner_query: str | None,
    include_players: bool,
) -> list[dict[str, Any]]:
    members = member_index(payload.get("members") or [])
    teams_out: list[dict[str, Any]] = []
    for team in payload.get("teams") or []:
        if owner_swid and not team_owned_by(team, owner_swid):
            continue
        owner = team_owner(team, members)
        if owner_query and not owner_matches(owner, owner_query):
            continue
        players = sort_players(
            [
                normalize_player(entry, bye_weeks=bye_weeks)
                for entry in ((team.get("roster") or {}).get("entries") or [])
            ]
        )
        row: dict[str, Any] = {
            "league_id": league_id,
            "league_name": league_name,
            "team_id": int(team.get("id") or 0),
            "team_name": str(team.get("name") or "").strip(),
            "abbrev": str(team.get("abbrev") or ""),
            "owner_display_name": owner.get("display_name") or "",
            "owner_name": owner_name(owner),
            "record": record_line(team),
            "points_for": round_stat(
                (team.get("record") or {}).get("overall", {}).get("pointsFor")
            ),
            "projected_rank": team.get("currentProjectedRank"),
            "waiver_rank": team.get("waiverRank"),
            "player_count": len(players),
        }
        if include_players:
            row["players"] = players
        teams_out.append(row)
    return teams_out
