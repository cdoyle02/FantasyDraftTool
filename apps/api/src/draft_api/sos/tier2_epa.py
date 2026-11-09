"""Tier 2 defensive EPA-allowed rates (QB/RB/WR/TE)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from draft_api.sos.calculate import (
    CompletedGame,
    Position,
    SosWindow,
    rank_defenses_shrunk,
    rated_through_week,
    resolve_sos_window,
    shrink_afpa,
    softness_bucket,
)
from draft_api.sos.nflverse import NFL_TEAMS, normalize_team
from draft_api.sos.tier1 import DefenseSoftness

EPA_POSITIONS: frozenset[Position] = frozenset({"QB", "RB", "WR", "TE"})
Tier2EpaPosition = Literal["QB", "RB", "WR", "TE"]


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_float(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


@dataclass(frozen=True, slots=True)
class EpaGameTotal:
    week: int
    offense: str
    defense: str
    total_epa: float


def _epa_column(position: Position) -> str:
    if position == "QB":
        return "passing_epa"
    if position == "RB":
        return "rushing_epa"
    if position in ("WR", "TE"):
        return "receiving_epa"
    raise ValueError(f"EPA allowed unsupported for position {position!r}")


def defensive_epa_allowed_per_game(
    stats_rows: list[dict[str, str | None]],
    *,
    position: Position,
) -> list[EpaGameTotal]:
    """Sum offensive EPA vs each defense per completed week (one row per game matchup)."""
    if position not in EPA_POSITIONS:
        raise ValueError(f"EPA allowed unsupported for position {position!r}")

    column = _epa_column(position)
    totals: dict[tuple[int, str, str], float] = defaultdict(float)

    for row in stats_rows:
        if (row.get("season_type") or "").upper() not in ("REG", "REGULAR"):
            continue
        row_pos = (row.get("position") or "").upper()
        if row_pos != position:
            continue
        week = _parse_int(row.get("week"))
        if week is None:
            continue
        offense = normalize_team(row.get("team") or "")
        defense = normalize_team(row.get("opponent_team") or "")
        if not offense or not defense:
            continue
        totals[(week, offense, defense)] += _parse_float(row.get(column))

    games: list[EpaGameTotal] = []
    for (week, offense, defense), total in sorted(totals.items()):
        games.append(
            EpaGameTotal(week=week, offense=offense, defense=defense, total_epa=total)
        )
    return games


def shrunk_defensive_epa(
    games: list[EpaGameTotal],
    *,
    position: Position,
    teams: list[str] | None = None,
) -> dict[str, float | None]:
    """Per-defense mean EPA allowed per game, shrunk toward league mean (k=SHRINK_K)."""
    _ = position
    team_list = teams or list(NFL_TEAMS)
    by_defense: dict[str, list[float]] = defaultdict(list)
    for game in games:
        by_defense[game.defense].append(game.total_epa)

    raw: dict[str, float | None] = {
        defense: (sum(vals) / len(vals) if vals else None) for defense, vals in by_defense.items()
    }
    present = [raw[t] for t in team_list if raw.get(t) is not None]
    prior = sum(present) / len(present) if present else 0.0

    counts: dict[str, int] = defaultdict(int)
    for game in games:
        counts[game.defense] += 1

    shrunk: dict[str, float | None] = {}
    for team in team_list:
        n = counts.get(team, 0)
        shrunk[team] = shrink_afpa(raw.get(team), prior, n)
    return shrunk


def build_defense_epa_softness_index(
    *,
    position: Position,
    window: SosWindow,
    games: list[CompletedGame],
    stats_rows: list[dict[str, str | None]],
    teams: list[str] | None = None,
    season: int | None = None,
) -> tuple[int, tuple[int, ...], dict[str, DefenseSoftness]]:
    """EPA-allowed defensive softness for the rating window (32-team rank buckets)."""
    if position not in EPA_POSITIONS:
        raise ValueError(f"Tier 2 EPA unsupported for position {position!r}")
    _ = season

    through = rated_through_week(games)
    rating_weeks_set = resolve_sos_window(window, through)
    rating_weeks = tuple(sorted(rating_weeks_set))
    epa_games = defensive_epa_allowed_per_game(stats_rows, position=position)
    filtered_epa = [g for g in epa_games if g.week in rating_weeks_set]

    team_list = list(teams) if teams is not None else list(NFL_TEAMS)
    shrunk = shrunk_defensive_epa(filtered_epa, position=position, teams=team_list)
    defense_ranks = rank_defenses_shrunk(shrunk, team_list)

    index: dict[str, DefenseSoftness] = {}
    scope = team_list
    for defense in scope:
        rank = defense_ranks.get(defense)
        if rank is None:
            continue
        softness, score = softness_bucket(rank)
        index[defense] = DefenseSoftness(
            defense=defense,
            rank=rank,
            softness=softness,
            softness_score=score,
        )
    return through, rating_weeks, index
