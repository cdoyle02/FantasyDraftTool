"""Pace tab — offensive plays per game and pass/run split."""

from __future__ import annotations

from dataclasses import dataclass

from draft_api.workbook.calculate import PassPlay
from draft_api.workbook.nflverse import WorkbookDataset

_EXCLUDED_PLAY_TYPES = frozenset({"kneel", "spike", "no_play"})


@dataclass(frozen=True, slots=True)
class CountablePlay:
    team: str
    week: int
    is_pass: bool
    play_type: str | None = None


@dataclass(frozen=True, slots=True)
class TeamPaceRow:
    team: str
    plays_per_game: float | None
    pass_rate: float | None
    run_rate: float | None


def _is_countable(play: CountablePlay) -> bool:
    if play.play_type is None:
        return True
    normalized = play.play_type.strip().lower()
    return normalized not in _EXCLUDED_PLAY_TYPES


def offensive_plays_per_game(
    plays: list[CountablePlay],
    *,
    team: str,
    weeks: set[int],
) -> tuple[float | None, float | None, float | None]:
    """Returns (plays/G, pass_rate, run_rate) for countable offensive snaps."""
    matched = [
        play
        for play in plays
        if play.team == team and play.week in weeks and _is_countable(play)
    ]
    if not matched:
        return None, None, None
    games = len({play.week for play in matched})
    pass_n = sum(1 for play in matched if play.is_pass)
    run_n = len(matched) - pass_n
    total = len(matched)
    plays_per_game = total / games
    pass_rate = pass_n / total if total else None
    run_rate = run_n / total if total else None
    return plays_per_game, pass_rate, run_rate


def plays_from_pass_plays(pass_plays: list[PassPlay]) -> list[CountablePlay]:
    return [
        CountablePlay(team=play.team, week=play.week, is_pass=play.is_pass)
        for play in pass_plays
    ]


def build_pace_table(dataset: WorkbookDataset, *, weeks: set[int]) -> list[TeamPaceRow]:
    countable = plays_from_pass_plays(dataset.pass_plays)
    rows: list[TeamPaceRow] = []
    for team in sorted(dataset.teams):
        plays_pg, pass_rate, run_rate = offensive_plays_per_game(
            countable, team=team, weeks=weeks
        )
        rows.append(
            TeamPaceRow(
                team=team,
                plays_per_game=round(plays_pg, 1) if plays_pg is not None else None,
                pass_rate=round(pass_rate, 3) if pass_rate is not None else None,
                run_rate=round(run_rate, 3) if run_rate is not None else None,
            )
        )
    return rows


def row_to_json(row: TeamPaceRow) -> dict[str, object]:
    return {
        "team": row.team,
        "playsPerGame": row.plays_per_game,
        "passRate": row.pass_rate,
        "runRate": row.run_rate,
    }
