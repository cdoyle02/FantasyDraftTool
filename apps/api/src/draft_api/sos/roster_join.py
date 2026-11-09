"""Join ESPN league rosters onto Tier 1 nflverse opportunity rows."""

from __future__ import annotations

from typing import Any

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.sos.calculate import Position
from draft_api.workbook.identity import normalize_team, player_join_key

JoinStats = dict[str, int]


def _position_matches(roster_slot: str, position: Position) -> bool:
    slot = (roster_slot or "").strip().upper()
    return slot == position


def _opportunity_index(opportunities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in opportunities:
        name = str(row.get("name") or "")
        team = str(row.get("team") or "")
        key = player_join_key(name, team)
        index[key] = row
    return index


def join_roster_opportunity(
    roster: list[EspnRosterPlayer],
    opportunities: list[dict[str, Any]],
    *,
    position: Position,
) -> tuple[list[dict[str, Any]], JoinStats]:
    """Overlay household ESPN roster players with nflverse opportunity metrics."""
    by_key = _opportunity_index(opportunities)
    stats: JoinStats = {"matched": 0, "unmatched": 0, "skippedPosition": 0}
    rows: list[dict[str, Any]] = []

    for player in roster:
        if not _position_matches(player.roster_slot, position):
            stats["skippedPosition"] += 1
            continue
        team = normalize_team(player.nfl_team)
        key = player_join_key(player.full_name, team)
        matched = by_key.get(key)
        if matched is not None:
            stats["matched"] += 1
            rows.append(
                {
                    **matched,
                    "playerId": player.player_id,
                    "name": player.full_name,
                    "team": team,
                    "position": position,
                    "joinStatus": "matched",
                    "lineupSlot": player.lineup_slot,
                    "injuryStatus": player.injury_status,
                    "espnTeamId": player.espn_team_id,
                }
            )
            continue
        stats["unmatched"] += 1
        rows.append(
            {
                "gsisId": None,
                "playerId": player.player_id,
                "name": player.full_name,
                "team": team,
                "position": position,
                "week": opportunities[0]["week"] if opportunities else None,
                "opponent": None,
                "opponentRank": None,
                "softness": None,
                "softnessScore": None,
                "usageShare": None,
                "opportunity": None,
                "bye": False,
                "joinStatus": "unmatched",
                "lineupSlot": player.lineup_slot,
                "injuryStatus": player.injury_status,
                "espnTeamId": player.espn_team_id,
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("opportunity") is None,
            -(row.get("opportunity") or 0.0),
            row.get("name") or "",
        )
    )
    return rows, stats
