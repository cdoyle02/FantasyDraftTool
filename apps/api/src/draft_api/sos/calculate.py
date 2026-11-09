"""Pure FPA / PAE strength-of-schedule calculator.

FPA (fantasy points allowed): mean full-PPR points a defense allowed to a
position across completed games. Rank 1 allows the most (easiest matchup).

PAE (points above expectation): for each completed game, points allowed minus
that offense's average at the position in its *other* completed games. Average
those residuals. Rank 1 is the softest defense relative to who it faced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Position = Literal["QB", "RB", "WR", "TE", "DST"]
Metric = Literal["fpa", "pae"]
Softness = Literal["soft", "neutral", "tough"]
SosWindow = Literal["l4", "l8", "season"]

SHRINK_K = 4

POSITIONS: tuple[Position, ...] = ("QB", "RB", "WR", "TE", "DST")
SKILL_POSITIONS: tuple[Position, ...] = ("QB", "RB", "WR", "TE")
WEEKS = range(1, 19)


@dataclass(frozen=True, slots=True)
class CompletedGame:
    """One team's offensive output against a defense in a completed game."""

    week: int
    offense: str
    defense: str
    points: dict[Position, float]


@dataclass(frozen=True, slots=True)
class SosWeekCell:
    week: int
    opponent: str | None
    opponent_rank: int | None
    opponent_value: float | None
    bye: bool
    in_window: bool


@dataclass(frozen=True, slots=True)
class SosTeamRow:
    team: str
    rank: int
    opponent_average: float | None
    weeks: list[SosWeekCell]


@dataclass(frozen=True, slots=True)
class SosPayload:
    season: int
    position: Position
    metric: Metric
    start_week: int
    end_week: int
    rated_through_week: int
    teams: list[SosTeamRow]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def offense_game_averages(
    games: list[CompletedGame],
    position: Position,
) -> dict[str, float]:
    """Mean points scored by each offense at `position` across completed games."""
    buckets: dict[str, list[float]] = {}
    for game in games:
        buckets.setdefault(game.offense, []).append(game.points.get(position, 0.0))
    return {team: sum(vals) / len(vals) for team, vals in buckets.items()}


def defensive_fpa(
    games: list[CompletedGame],
    position: Position,
) -> dict[str, float]:
    """Average points allowed by each defense to `position`."""
    buckets: dict[str, list[float]] = {}
    for game in games:
        buckets.setdefault(game.defense, []).append(game.points.get(position, 0.0))
    return {team: sum(vals) / len(vals) for team, vals in buckets.items()}


def defensive_pae(
    games: list[CompletedGame],
    position: Position,
) -> dict[str, float]:
    """Schedule-adjusted points above expectation allowed by each defense.

    For each game: allowed − leave-one-out offense average at the position.
    Games where the offense has no other completed game are skipped.
    """
    by_offense: dict[str, list[CompletedGame]] = {}
    for game in games:
        by_offense.setdefault(game.offense, []).append(game)

    residuals: dict[str, list[float]] = {}
    for game in games:
        siblings = by_offense[game.offense]
        if len(siblings) < 2:
            continue
        others = [
            g.points.get(position, 0.0)
            for g in siblings
            if not (g.week == game.week and g.defense == game.defense)
        ]
        if not others:
            continue
        expected = sum(others) / len(others)
        allowed = game.points.get(position, 0.0)
        residuals.setdefault(game.defense, []).append(allowed - expected)

    return {team: sum(vals) / len(vals) for team, vals in residuals.items()}


def shrink_afpa(
    raw: float | None,
    prior: float,
    n: int,
    k: int = SHRINK_K,
) -> float | None:
    """Empirical-Bayes shrink toward league-position prior; n=0 → prior."""
    if n <= 0:
        return prior
    if raw is None:
        return prior
    return (n * raw + k * prior) / (n + k)


def softness_bucket(rank: int) -> tuple[Softness, float]:
    """Map defense rank (1 = softest) to bucket + linear softness score."""
    if rank <= 7:
        return "soft", 1.0
    if rank >= 26:
        return "tough", 0.0
    return "neutral", 0.5


def resolve_sos_window(mode: SosWindow, rated_through_week: int) -> set[int]:
    """Completed weeks included in the rolling rating window."""
    if rated_through_week <= 0:
        return set()
    if mode == "season":
        return set(range(1, rated_through_week + 1))
    span = 4 if mode == "l4" else 8
    start = max(1, rated_through_week - span + 1)
    return set(range(start, rated_through_week + 1))


def defensive_game_counts(
    games: list[CompletedGame],
    position: Position,
) -> dict[str, int]:
    """Number of completed games each defense played in `games`."""
    counts: dict[str, int] = {}
    for game in games:
        counts[game.defense] = counts.get(game.defense, 0) + 1
    return counts


def shrunk_defensive_afpa(
    games: list[CompletedGame],
    position: Position,
    *,
    teams: list[str],
) -> dict[str, float]:
    """Raw FPA over `games`, shrunk toward the league mean with k=SHRINK_K."""
    raw = defensive_fpa(games, position)
    counts = defensive_game_counts(games, position)
    present = [raw[t] for t in teams if t in raw]
    prior = sum(present) / len(present) if present else 0.0
    shrunk: dict[str, float] = {}
    for team in teams:
        n = counts.get(team, 0)
        shrunk[team] = shrink_afpa(raw.get(team), prior, n)  # type: ignore[assignment]
    return shrunk


def rank_defenses_shrunk(
    values: dict[str, float | None],
    teams: list[str] | None = None,
) -> dict[str, int]:
    """Rank 1 = highest shrunk aFPA (softest). None/missing sort last."""
    team_list = teams or sorted(values)
    present = [(team, values[team]) for team in team_list if team in values and values[team] is not None]
    present.sort(key=lambda item: (-float(item[1]), item[0]))  # type: ignore[arg-type]
    ranks: dict[str, int] = {}
    for index, (team, _value) in enumerate(present, start=1):
        ranks[team] = index
    missing = sorted(team for team in team_list if team not in ranks)
    next_rank = len(ranks) + 1
    for team in missing:
        ranks[team] = next_rank
        next_rank += 1
    return ranks


def rank_defenses(values: dict[str, float], teams: list[str]) -> dict[str, int]:
    """Rank 1 = highest value (easiest). Missing teams get the worst remaining ranks."""
    present = [(team, values[team]) for team in teams if team in values]
    present.sort(key=lambda item: (-item[1], item[0]))
    ranks: dict[str, int] = {}
    for index, (team, _value) in enumerate(present, start=1):
        ranks[team] = index
    missing = sorted(team for team in teams if team not in ranks)
    next_rank = len(ranks) + 1
    for team in missing:
        ranks[team] = next_rank
        next_rank += 1
    return ranks


def build_schedule(
    games: list[CompletedGame],
    *,
    season_schedule: dict[str, dict[int, str | None]] | None = None,
    teams: list[str] | None = None,
) -> dict[str, dict[int, str | None]]:
    """Team → week → opponent abbrev (None = bye).

    Prefer an explicit season schedule (includes future/unplayed weeks). When
    omitted, derive opponents only from completed games and leave other weeks
    as bye/unknown None.
    """
    if season_schedule is not None:
        return {
            team: {week: season_schedule.get(team, {}).get(week) for week in WEEKS}
            for team in (teams or sorted(season_schedule))
        }

    derived: dict[str, dict[int, str | None]] = {}
    all_teams = set(teams or [])
    for game in games:
        all_teams.add(game.offense)
        all_teams.add(game.defense)
        derived.setdefault(game.offense, {})[game.week] = game.defense
        derived.setdefault(game.defense, {})[game.week] = game.offense
    return {
        team: {week: derived.get(team, {}).get(week) for week in WEEKS}
        for team in sorted(all_teams)
    }


def rated_through_week(games: list[CompletedGame]) -> int:
    if not games:
        return 0
    return max(game.week for game in games)


def build_sos_payload(
    *,
    season: int,
    position: Position,
    metric: Metric,
    start_week: int,
    end_week: int,
    games: list[CompletedGame],
    season_schedule: dict[str, dict[int, str | None]] | None = None,
    teams: list[str] | None = None,
) -> SosPayload:
    """Build the ranked team × week strength-of-schedule grid."""
    if start_week < 1 or end_week > 18 or start_week > end_week:
        raise ValueError(f"invalid week window {start_week}-{end_week}")
    if position not in POSITIONS:
        raise ValueError(f"unsupported position {position!r}")
    if metric not in ("fpa", "pae"):
        raise ValueError(f"unsupported metric {metric!r}")

    schedule = build_schedule(games, season_schedule=season_schedule, teams=teams)
    team_list = teams or sorted(schedule)
    values = (
        defensive_fpa(games, position)
        if metric == "fpa"
        else defensive_pae(games, position)
    )
    defense_ranks = rank_defenses(values, team_list)

    rows: list[SosTeamRow] = []
    for team in team_list:
        week_cells: list[SosWeekCell] = []
        window_values: list[float] = []
        for week in WEEKS:
            opponent = schedule.get(team, {}).get(week)
            bye = opponent is None
            in_window = start_week <= week <= end_week
            opp_value = None if bye or opponent is None else values.get(opponent)
            opp_rank = None if bye or opponent is None else defense_ranks.get(opponent)
            if in_window and not bye and opp_value is not None:
                window_values.append(opp_value)
            week_cells.append(
                SosWeekCell(
                    week=week,
                    opponent=opponent,
                    opponent_rank=opp_rank,
                    opponent_value=opp_value,
                    bye=bye,
                    in_window=in_window,
                )
            )
        rows.append(
            SosTeamRow(
                team=team,
                rank=0,  # filled after sort
                opponent_average=_mean(window_values),
                weeks=week_cells,
            )
        )

    # Easiest first: highest opponent average. Missing average sorts last.
    # Unique ranks via team abbrev tie-break.
    rows.sort(
        key=lambda row: (
            row.opponent_average is None,
            -(row.opponent_average or 0.0),
            row.team,
        )
    )
    ranked = [
        SosTeamRow(
            team=row.team,
            rank=index,
            opponent_average=row.opponent_average,
            weeks=row.weeks,
        )
        for index, row in enumerate(rows, start=1)
    ]

    return SosPayload(
        season=season,
        position=position,
        metric=metric,
        start_week=start_week,
        end_week=end_week,
        rated_through_week=rated_through_week(games),
        teams=ranked,
    )


def sos_payload_to_dict(
    payload: SosPayload,
    *,
    fetched_at: str,
    source: str,
    stale: bool,
) -> dict:
    """Serialize for the HTTP response (camelCase keys)."""
    return {
        "season": payload.season,
        "position": payload.position,
        "metric": payload.metric,
        "startWeek": payload.start_week,
        "endWeek": payload.end_week,
        "ratedThroughWeek": payload.rated_through_week,
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
                        "opponentRank": cell.opponent_rank,
                        "opponentValue": cell.opponent_value,
                        "bye": cell.bye,
                        "inWindow": cell.in_window,
                    }
                    for cell in row.weeks
                ],
            }
            for row in payload.teams
        ],
    }
