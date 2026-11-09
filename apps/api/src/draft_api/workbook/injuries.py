"""Workbook injuries tab — normalize ESPN roster injury fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from draft_api.espn_available_dst import default_http_json
from draft_api.espn_roster import (
    HttpJsonGetter,
    _auth_headers,
    _league_url,
    _nfl_team,
    parse_league_roster,
)
from draft_api.workbook.identity import normalize_team

STATUS_SEVERITY: dict[str, int] = {
    "OUT": 0,
    "O": 0,
    "DOUBTFUL": 1,
    "D": 1,
    "QUESTIONABLE": 2,
    "Q": 2,
    "PROBABLE": 3,
    "P": 3,
}


@dataclass(frozen=True, slots=True)
class InjuryRow:
    player_id: int
    name: str
    team: str
    status: str
    body_part: str | None
    practice: str | None
    game_status: str | None


class InjuriesFetchError(RuntimeError):
    """Raised when ESPN injury fetch fails."""


def _severity(status: str) -> int:
    return STATUS_SEVERITY.get(status.strip().upper(), 99)


def _parse_practice(player: dict[str, Any]) -> str | None:
    for key in ("injuryPractice", "practiceStatus", "practiceParticipation"):
        value = player.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            name = value.get("name") or value.get("description")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def _parse_game_status(player: dict[str, Any]) -> str | None:
    injury = player.get("injuryStatus")
    if isinstance(injury, dict):
        name = injury.get("type") or injury.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    status_block = player.get("status")
    if isinstance(status_block, dict):
        name = status_block.get("type") or status_block.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def parse_injuries_from_roster_payload(payload: dict[str, Any]) -> list[InjuryRow]:
    """Extract injury rows from an ESPN ``mTeam`` + ``mRoster`` payload."""
    rows: list[InjuryRow] = []
    teams = payload.get("teams")
    if not isinstance(teams, list):
        raise InjuriesFetchError("ESPN returned an unexpected payload")

    for team in teams:
        if not isinstance(team, dict):
            continue
        roster = team.get("roster") if isinstance(team.get("roster"), dict) else {}
        for entry in roster.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            pool = (
                entry.get("playerPoolEntry")
                if isinstance(entry.get("playerPoolEntry"), dict)
                else {}
            )
            player = pool.get("player") if isinstance(pool.get("player"), dict) else {}
            if not player:
                continue
            status_raw = player.get("injuryStatus")
            status = ""
            if isinstance(status_raw, str):
                status = status_raw.strip()
            elif isinstance(status_raw, dict):
                status = str(status_raw.get("abbreviation") or status_raw.get("name") or "").strip()
            if not status:
                continue
            try:
                player_id = int(entry.get("playerId") or player.get("id"))
            except (TypeError, ValueError):
                continue
            body = player.get("injuryBodyPart") or player.get("injuryType")
            body_part = str(body).strip() if body else None
            team_code = normalize_team(_nfl_team(player.get("proTeamId")))
            rows.append(
                InjuryRow(
                    player_id=player_id,
                    name=str(player.get("fullName") or "Unknown"),
                    team=team_code,
                    status=status,
                    body_part=body_part,
                    practice=_parse_practice(player),
                    game_status=_parse_game_status(player),
                )
            )
    rows.sort(key=lambda row: (row.team, _severity(row.status), row.name))
    return rows


def fetch_week_injuries(
    *,
    league_id: str,
    season: int,
    week: int,
    espn_s2: str,
    swid: str,
    http_json: HttpJsonGetter | None = None,
) -> list[InjuryRow]:
    """Fetch league roster injuries (`week` is board context only for now)."""
    del week  # reserved for future inactives / week-scoped feeds
    url = _league_url(league_id=league_id, season=season, views=["mTeam", "mRoster"])
    getter = http_json or default_http_json
    try:
        payload = getter(url, _auth_headers(espn_s2=espn_s2, swid=swid))
    except Exception as exc:
        raise InjuriesFetchError(f"ESPN request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise InjuriesFetchError("ESPN returned an unexpected payload")
    # Reuse roster team list validation
    parse_league_roster(payload)
    return parse_injuries_from_roster_payload(payload)


def row_to_json(row: InjuryRow) -> dict[str, object]:
    return {
        "playerId": row.player_id,
        "name": row.name,
        "team": row.team,
        "status": row.status,
        "bodyPart": row.body_part,
        "practice": row.practice,
        "gameStatus": row.game_status,
    }
