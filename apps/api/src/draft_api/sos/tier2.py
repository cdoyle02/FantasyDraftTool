"""Tier 2 strength-of-schedule: EPA allowed + snap-filtered opportunity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from draft_api.implied_totals import GameLine
from draft_api.sos.calculate import (
    SHRINK_K,
    WEEKS,
    CompletedGame,
    Position,
    SosWindow,
    Softness,
    _mean,
    build_schedule,
    rank_defenses_shrunk,
    rated_through_week,
    resolve_sos_window,
    softness_bucket,
)
from draft_api.sos.tier1 import DefenseSoftness
from draft_api.sos.tier2_epa import (
    EPA_POSITIONS,
    defensive_epa_allowed_per_game,
    shrunk_defensive_epa,
)
from draft_api.sos.tier2_game_script import (
    adjust_softness_score,
    find_game_line_for_matchup,
    implied_points_for_team,
)
from draft_api.sos.tier2_snap import DEFAULT_MIN_OFFENSE_SNAP_PCT
from draft_api.sos.nflverse import NFL_TEAMS
from draft_api.sos.usage import PlayerUsage

TIER2_POSITIONS: frozenset[Position] = EPA_POSITIONS


@dataclass(frozen=True, slots=True)
class Tier2WeekCell:
    week: int
    opponent: str | None
    shrunk_epa: float | None
    rank: int | None
    softness: Softness | None
    softness_score: float | None
    bye: bool
    in_window: bool


@dataclass(frozen=True, slots=True)
class Tier2TeamRow:
    team: str
    rank: int
    opponent_average: float | None
    weeks: list[Tier2WeekCell]


@dataclass(frozen=True, slots=True)
class Tier2Payload:
    season: int
    position: Position
    window: SosWindow
    start_week: int
    end_week: int
    rated_through_week: int
    rating_weeks: tuple[int, ...]
    shrink_k: int
    teams: list[Tier2TeamRow]


def build_tier2_grid(
    *,
    season: int,
    position: Position,
    window: SosWindow,
    start_week: int,
    end_week: int,
    games: list[CompletedGame],
    stats_rows: list[dict[str, str | None]],
    season_schedule: dict[str, dict[int, str | None]] | None = None,
    teams: list[str] | None = None,
    shrink_k: int | None = None,
) -> Tier2Payload:
    if position not in TIER2_POSITIONS:
        raise ValueError(
            f"Tier 2 grid supports QB, RB, WR, and TE only (got {position!r})"
        )
    if start_week < 1 or end_week > 18 or start_week > end_week:
        raise ValueError(f"invalid week window {start_week}-{end_week}")
    if window not in ("l4", "l8", "season"):
        raise ValueError(f"unsupported window {window!r}")

    k = SHRINK_K if shrink_k is None else shrink_k
    through = rated_through_week(games)
    rating_weeks_set = resolve_sos_window(window, through)
    rating_weeks = tuple(sorted(rating_weeks_set))

    epa_games = defensive_epa_allowed_per_game(stats_rows, position=position)
    filtered_epa = [g for g in epa_games if g.week in rating_weeks_set]
    team_list = teams or list(NFL_TEAMS)
    shrunk = shrunk_defensive_epa(filtered_epa, position=position, teams=team_list)
    defense_ranks = rank_defenses_shrunk(shrunk, team_list)

    schedule = build_schedule(games, season_schedule=season_schedule, teams=teams)
    display_teams = teams or sorted(schedule)

    rows: list[Tier2TeamRow] = []
    for team in display_teams:
        week_cells: list[Tier2WeekCell] = []
        window_values: list[float] = []
        for week in WEEKS:
            opponent = schedule.get(team, {}).get(week)
            bye = opponent is None
            in_window = start_week <= week <= end_week
            opp_epa = None if bye or opponent is None else shrunk.get(opponent)
            opp_rank = None if bye or opponent is None else defense_ranks.get(opponent)
            softness: Softness | None = None
            softness_score: float | None = None
            if opp_rank is not None:
                softness, softness_score = softness_bucket(opp_rank)
            if in_window and not bye and opp_epa is not None:
                window_values.append(float(opp_epa))
            week_cells.append(
                Tier2WeekCell(
                    week=week,
                    opponent=opponent,
                    shrunk_epa=opp_epa,
                    rank=opp_rank,
                    softness=softness,
                    softness_score=softness_score,
                    bye=bye,
                    in_window=in_window,
                )
            )
        rows.append(
            Tier2TeamRow(
                team=team,
                rank=0,
                opponent_average=_mean(window_values),
                weeks=week_cells,
            )
        )

    rows.sort(
        key=lambda row: (
            row.opponent_average is None,
            -(row.opponent_average or 0.0),
            row.team,
        )
    )
    ranked = [
        Tier2TeamRow(
            team=row.team,
            rank=index,
            opponent_average=row.opponent_average,
            weeks=row.weeks,
        )
        for index, row in enumerate(rows, start=1)
    ]

    return Tier2Payload(
        season=season,
        position=position,
        window=window,
        start_week=start_week,
        end_week=end_week,
        rated_through_week=through,
        rating_weeks=rating_weeks,
        shrink_k=k,
        teams=ranked,
    )


def build_tier2_player_opportunity(
    *,
    position: Position,
    usage_index: list[PlayerUsage],
    defense_softness: dict[str, DefenseSoftness],
    schedule: dict[str, dict[int, str | None]],
    week: int,
    game_lines: list[GameLine] | None = None,
    snap_filtered: bool = False,
    min_offense_snap_pct: float = DEFAULT_MIN_OFFENSE_SNAP_PCT,
) -> list[dict[str, Any]]:
    """Opportunity = game-script-adjusted softness × usage share."""
    _ = position, snap_filtered
    odds_games = game_lines
    rows: list[dict[str, Any]] = []
    for player in usage_index:
        opponent = schedule.get(player.team, {}).get(week)
        base: dict[str, Any] = {
            "gsisId": player.gsis_id,
            "playerId": None,
            "name": player.player_name,
            "team": player.team,
            "position": player.position,
            "week": week,
            "opponent": opponent,
            "opponentRank": None,
            "softness": None,
            "softnessScore": None,
            "usageShare": player.usage_share,
            "gameScriptDelta": 0.0,
            "adjustedSoftness": None,
            "opportunity": None,
            "bye": opponent is None,
        }
        if opponent is None:
            rows.append(base)
            continue

        softness_row = defense_softness.get(opponent)
        softness = softness_row.softness if softness_row else None
        softness_score = softness_row.softness_score if softness_row else None
        opp_rank = softness_row.rank if softness_row else None

        game_script_delta = 0.0
        adjusted_softness = softness_score
        row_script_applied = False
        if odds_games and softness_score is not None:
            game = find_game_line_for_matchup(
                odds_games, team=player.team, opponent=opponent
            )
            team_implied = (
                implied_points_for_team(game, team=player.team) if game is not None else None
            )
            adjusted, game_script_delta, row_script_applied = adjust_softness_score(
                softness_score=softness_score,
                team_implied=team_implied,
            )
            adjusted_softness = adjusted

        opportunity = None
        if player.usage_share is not None and adjusted_softness is not None:
            opportunity = adjusted_softness * player.usage_share

        base.update(
            {
                "opponentRank": opp_rank,
                "softness": softness,
                "softnessScore": softness_score,
                "gameScriptDelta": game_script_delta,
                "adjustedSoftness": adjusted_softness,
                "opportunity": opportunity,
                "minOffenseSnapPct": min_offense_snap_pct,
                "gameScriptApplied": row_script_applied,
            }
        )
        rows.append(base)

    rows.sort(
        key=lambda row: (
            row["opportunity"] is None,
            -(row["opportunity"] or 0.0),
            row["name"],
        )
    )
    return rows


def tier2_payload_to_dict(
    payload: Tier2Payload,
    *,
    fetched_at: str,
    source: str,
    stale: bool,
    softness_metric: str = "epa_allowed",
) -> dict[str, Any]:
    return {
        "season": payload.season,
        "position": payload.position,
        "window": payload.window,
        "startWeek": payload.start_week,
        "endWeek": payload.end_week,
        "ratedThroughWeek": payload.rated_through_week,
        "ratingWeeks": list(payload.rating_weeks),
        "shrinkK": payload.shrink_k,
        "softnessMetric": softness_metric,
        "fetchedAt": fetched_at,
        "source": source,
        "stale": stale,
        "teams": [
            {
                "team": row.team,
                "rank": row.rank,
                "opponentAverage": row.opponent_average,
                "weeks": [
                    {
                        "week": cell.week,
                        "opponent": cell.opponent,
                        "shrunkEpa": cell.shrunk_epa,
                        "rank": cell.rank,
                        "softness": cell.softness,
                        "softnessScore": cell.softness_score,
                        "bye": cell.bye,
                        "inWindow": cell.in_window,
                    }
                    for cell in row.weeks
                ],
            }
            for row in payload.teams
        ],
    }
