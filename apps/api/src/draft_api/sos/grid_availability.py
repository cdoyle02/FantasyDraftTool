"""Annotate SoS team-grid rows with primary player + league availability."""

from __future__ import annotations

from typing import Any, Literal

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.workbook.identity import normalize_team, player_join_key

LeagueAvailability = Literal["available", "on_roster", "taken", "unknown"]


def primary_by_team(
    opportunity_players: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Best opportunity row per NFL team (opportunities are pre-sorted best-first)."""
    out: dict[str, dict[str, Any]] = {}
    for row in opportunity_players:
        team = normalize_team(str(row.get("team") or ""))
        if not team or team in out:
            continue
        out[team] = row
    return out


def _roster_index(
    roster: list[EspnRosterPlayer],
    *,
    position: str,
) -> dict[str, EspnRosterPlayer]:
    """Join-key → rostered player at the selected position (or DST)."""
    want = position.upper()
    index: dict[str, EspnRosterPlayer] = {}
    for player in roster:
        slot = (player.roster_slot or "").strip().upper()
        if want == "DST":
            if slot not in ("DST", "D/ST", "DEF"):
                continue
        elif slot != want:
            continue
        key = player_join_key(player.full_name, normalize_team(player.nfl_team))
        index[key] = player
    return index


def _dst_roster_by_team(roster: list[EspnRosterPlayer]) -> dict[str, EspnRosterPlayer]:
    by_team: dict[str, EspnRosterPlayer] = {}
    for player in roster:
        slot = (player.roster_slot or "").strip().upper()
        if slot not in ("DST", "D/ST", "DEF"):
            continue
        team = normalize_team(player.nfl_team)
        if team and team not in by_team:
            by_team[team] = player
    return by_team


def league_availability_for_player(
    *,
    join_key: str,
    roster_by_key: dict[str, EspnRosterPlayer],
    owner_team_id: int | None,
) -> LeagueAvailability:
    hit = roster_by_key.get(join_key)
    if hit is None:
        return "available"
    if owner_team_id is not None and hit.espn_team_id == owner_team_id:
        return "on_roster"
    return "taken"


def annotate_grid_teams(
    teams: list[dict[str, Any]],
    *,
    position: str,
    opportunity_players: list[dict[str, Any]] | None,
    roster: list[EspnRosterPlayer] | None,
    owner_team_id: int | None,
) -> list[dict[str, Any]]:
    """Mutate-copy team rows with primaryPlayer + leagueAvailability."""
    pos = position.upper()
    primary = primary_by_team(opportunity_players or []) if opportunity_players else {}
    roster_by_key = _roster_index(roster or [], position=pos) if roster is not None else {}
    dst_by_team = _dst_roster_by_team(roster or []) if roster is not None and pos == "DST" else {}

    annotated: list[dict[str, Any]] = []
    for row in teams:
        team = normalize_team(str(row.get("team") or ""))
        copy = dict(row)
        if pos == "DST":
            primary_player = {
                "name": f"{team} D/ST" if team else "D/ST",
                "playerId": None,
                "position": "DST",
                "team": team,
            }
            if roster is None:
                availability: LeagueAvailability = "unknown"
            else:
                hit = dst_by_team.get(team)
                if hit is None:
                    availability = "available"
                elif owner_team_id is not None and hit.espn_team_id == owner_team_id:
                    availability = "on_roster"
                else:
                    availability = "taken"
                if hit is not None:
                    primary_player["playerId"] = hit.player_id
                    primary_player["name"] = hit.full_name
        else:
            opp = primary.get(team)
            if not opp:
                copy["primaryPlayer"] = None
                copy["leagueAvailability"] = "unknown"
                annotated.append(copy)
                continue
            name = str(opp.get("name") or "")
            primary_player = {
                "name": name,
                "playerId": opp.get("playerId"),
                "position": pos,
                "team": team,
                "gsisId": opp.get("gsisId"),
            }
            if roster is None:
                availability = "unknown"
            else:
                key = player_join_key(name, team)
                availability = league_availability_for_player(
                    join_key=key,
                    roster_by_key=roster_by_key,
                    owner_team_id=owner_team_id,
                )
                hit = roster_by_key.get(key)
                if hit is not None:
                    primary_player["playerId"] = hit.player_id
        copy["primaryPlayer"] = primary_player
        copy["leagueAvailability"] = availability
        annotated.append(copy)
    return annotated
