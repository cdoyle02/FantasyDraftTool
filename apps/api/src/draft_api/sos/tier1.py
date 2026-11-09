"""Tier 1 strength-of-schedule: shrunk aFPA + softness buckets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from draft_api.sos.calculate import (
    POSITIONS,
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
    shrunk_defensive_afpa,
    softness_bucket,
)


@dataclass(frozen=True, slots=True)
class Tier1WeekCell:
    week: int
    opponent: str | None
    shrunk_afpa: float | None
    rank: int | None
    softness: Softness | None
    softness_score: float | None
    bye: bool
    in_window: bool


@dataclass(frozen=True, slots=True)
class Tier1TeamRow:
    team: str
    rank: int
    opponent_average: float | None
    weeks: list[Tier1WeekCell]


@dataclass(frozen=True, slots=True)
class Tier1Payload:
    season: int
    position: Position
    window: SosWindow
    start_week: int
    end_week: int
    rated_through_week: int
    rating_weeks: tuple[int, ...]
    shrink_k: int
    teams: list[Tier1TeamRow]


def _games_in_weeks(games: list[CompletedGame], weeks: set[int]) -> list[CompletedGame]:
    return [game for game in games if game.week in weeks]


def build_tier1_grid(
    *,
    season: int,
    position: Position,
    window: SosWindow,
    start_week: int,
    end_week: int,
    games: list[CompletedGame],
    season_schedule: dict[str, dict[int, str | None]] | None = None,
    teams: list[str] | None = None,
    shrink_k: int | None = None,
) -> Tier1Payload:
    """Team × week grid using shrunk defensive aFPA over the rating window."""
    from draft_api.sos.calculate import SHRINK_K

    if start_week < 1 or end_week > 18 or start_week > end_week:
        raise ValueError(f"invalid week window {start_week}-{end_week}")
    if position not in POSITIONS:
        raise ValueError(f"unsupported position {position!r}")
    if window not in ("l4", "l8", "season"):
        raise ValueError(f"unsupported window {window!r}")

    k = SHRINK_K if shrink_k is None else shrink_k
    through = rated_through_week(games)
    rating_weeks_set = resolve_sos_window(window, through)
    rating_weeks = tuple(sorted(rating_weeks_set))
    window_games = _games_in_weeks(games, rating_weeks_set)

    schedule = build_schedule(games, season_schedule=season_schedule, teams=teams)
    team_list = teams or sorted(schedule)
    shrunk = shrunk_defensive_afpa(window_games, position, teams=team_list)
    defense_ranks = rank_defenses_shrunk(shrunk, team_list)

    rows: list[Tier1TeamRow] = []
    for team in team_list:
        week_cells: list[Tier1WeekCell] = []
        window_values: list[float] = []
        for week in WEEKS:
            opponent = schedule.get(team, {}).get(week)
            bye = opponent is None
            in_window = start_week <= week <= end_week
            opp_afpa = None if bye or opponent is None else shrunk.get(opponent)
            opp_rank = None if bye or opponent is None else defense_ranks.get(opponent)
            softness: Softness | None = None
            softness_score: float | None = None
            if opp_rank is not None:
                softness, softness_score = softness_bucket(opp_rank)
            if in_window and not bye and opp_afpa is not None:
                window_values.append(opp_afpa)
            week_cells.append(
                Tier1WeekCell(
                    week=week,
                    opponent=opponent,
                    shrunk_afpa=opp_afpa,
                    rank=opp_rank,
                    softness=softness,
                    softness_score=softness_score,
                    bye=bye,
                    in_window=in_window,
                )
            )
        rows.append(
            Tier1TeamRow(
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
        Tier1TeamRow(
            team=row.team,
            rank=index,
            opponent_average=row.opponent_average,
            weeks=row.weeks,
        )
        for index, row in enumerate(rows, start=1)
    ]

    return Tier1Payload(
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


def tier1_payload_to_dict(
    payload: Tier1Payload,
    *,
    fetched_at: str,
    source: str,
    stale: bool,
) -> dict[str, Any]:
    """Serialize Tier 1 grid for HTTP (camelCase keys)."""
    return {
        "season": payload.season,
        "position": payload.position,
        "window": payload.window,
        "startWeek": payload.start_week,
        "endWeek": payload.end_week,
        "ratedThroughWeek": payload.rated_through_week,
        "ratingWeeks": list(payload.rating_weeks),
        "shrinkK": payload.shrink_k,
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
                        "shrunkAfpa": cell.shrunk_afpa,
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
