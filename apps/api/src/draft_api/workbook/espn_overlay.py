"""Map ESPN roster/FA players onto Workbook matchup rows for P1 highlights."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.workbook.identity import normalize_team

HighlightRole = Literal["roster", "free_agent", "waiver"]

JoinStats = dict[str, int]


@dataclass(frozen=True, slots=True)
class WorkbookHighlight:
    player_id: int
    display_name: str
    nfl_team: str
    matchup_team: str
    opponent: str
    role: HighlightRole
    roster_slot: str | None


def _team_opponent_index(games: list[dict[str, Any]]) -> dict[str, str]:
    """Map normalized nflverse team abbrev → opponent this week."""
    index: dict[str, str] = {}
    for game in games:
        for row in game.get("rows") or []:
            if not isinstance(row, dict):
                continue
            team = row.get("team")
            opponent = row.get("opponent")
            if not team or not opponent:
                continue
            index[normalize_team(str(team))] = normalize_team(str(opponent))
    return index


def _role_for_player(player: EspnRosterPlayer) -> HighlightRole:
    if player.availability == "WAIVERS":
        return "waiver"
    if player.availability == "FREEAGENT":
        return "free_agent"
    return "roster"


def build_highlights(
    *,
    games: list[dict[str, Any]],
    roster: list[EspnRosterPlayer],
    free_agents: list[EspnRosterPlayer],
    owner_team_id: int | None,
    include_fa: bool = True,
) -> tuple[list[WorkbookHighlight], JoinStats]:
    """Attach roster / FA players to teams on this week's board."""
    board = _team_opponent_index(games)
    stats: JoinStats = {"matched": 0, "unmatched_team": 0, "unmatched_name_only": 0}
    highlights: list[WorkbookHighlight] = []

    def consider(player: EspnRosterPlayer) -> None:
        team = normalize_team(player.nfl_team)
        opponent = board.get(team)
        if opponent is None:
            stats["unmatched_team"] += 1
            return
        stats["matched"] += 1
        highlights.append(
            WorkbookHighlight(
                player_id=player.player_id,
                display_name=player.full_name,
                nfl_team=team,
                matchup_team=team,
                opponent=opponent,
                role=_role_for_player(player),
                roster_slot=player.roster_slot,
            )
        )

    for player in roster:
        if owner_team_id is not None and player.espn_team_id != owner_team_id:
            continue
        consider(player)

    if include_fa:
        for player in free_agents:
            consider(player)

    return highlights, stats


def highlights_to_json(
    highlights: list[WorkbookHighlight],
    join_stats: JoinStats,
) -> dict[str, Any]:
    """CamelCase payload fragment for matchups API merge."""
    return {
        "highlights": [
            {
                "playerId": h.player_id,
                "displayName": h.display_name,
                "nflTeam": h.nfl_team,
                "matchupTeam": h.matchup_team,
                "opponent": h.opponent,
                "role": h.role,
                "rosterSlot": h.roster_slot,
            }
            for h in highlights
        ],
        "joinStats": dict(join_stats),
    }
