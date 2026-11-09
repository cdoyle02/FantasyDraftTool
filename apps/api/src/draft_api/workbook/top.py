"""Time of possession (TOP) tab — PBP drive seconds or plays-share proxy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from draft_api.workbook.calculate import TeamRateSlice
from draft_api.workbook.nflverse import WorkbookDataset

TopMethod = Literal["pbp_drive", "plays_share_proxy"]


@dataclass(frozen=True, slots=True)
class DrivePossession:
    """One offensive drive's possession time (seconds) in nflverse PBP."""

    team: str
    week: int
    seconds: float
    game_id: str | None = None


@dataclass(frozen=True, slots=True)
class TeamTopSlice:
    team: str
    top_pct: float | None
    method: TopMethod
    sample_games: int


def top_plays_share_proxy(off_plays: int, opp_off_plays: int) -> float:
    """Share of offensive plays (0–1) as a TOP proxy for one game."""
    total = off_plays + opp_off_plays
    if total <= 0:
        return 0.0
    return off_plays / total


def top_from_drive_seconds(
    drives: list[DrivePossession],
    *,
    team: str,
    weeks: set[int],
    schedule: dict[int, dict[str, str | None]],
) -> tuple[float | None, int]:
    """Mean per-game possession share (0–1) from summed drive seconds."""
    seconds_by_team_week: dict[tuple[str, int], float] = defaultdict(float)
    for drive in drives:
        if drive.week not in weeks:
            continue
        seconds_by_team_week[(drive.team, drive.week)] += drive.seconds

    shares: list[float] = []
    for week in sorted(weeks):
        opponent = (schedule.get(week) or {}).get(team)
        if not opponent:
            continue
        team_sec = seconds_by_team_week.get((team, week), 0.0)
        opp_sec = seconds_by_team_week.get((opponent, week), 0.0)
        combined = team_sec + opp_sec
        if combined <= 0:
            continue
        shares.append(team_sec / combined)
    if not shares:
        return None, 0
    return sum(shares) / len(shares), len(shares)


def _off_plays_by_team_week(slices: list[TeamRateSlice]) -> dict[tuple[str, int], int]:
    out: dict[tuple[str, int], int] = {}
    for sl in slices:
        plays = int((sl.pass_plays or 0.0) + (sl.run_plays or 0.0))
        out[(sl.team, sl.week)] = plays
    return out


def _top_from_plays_proxy(
    dataset: WorkbookDataset,
    *,
    team: str,
    weeks: set[int],
    plays_by_team_week: dict[tuple[str, int], int],
) -> tuple[float | None, int]:
    shares: list[float] = []
    for week in sorted(weeks):
        opponent = (dataset.schedule.get(week) or {}).get(team)
        if not opponent:
            continue
        off = plays_by_team_week.get((team, week), 0)
        opp_off = plays_by_team_week.get((opponent, week), 0)
        if off + opp_off == 0:
            continue
        shares.append(top_plays_share_proxy(off, opp_off))
    if not shares:
        return None, 0
    return sum(shares) / len(shares), len(shares)


def build_top_table(
    dataset: WorkbookDataset,
    *,
    weeks: set[int],
    drive_possessions: list[DrivePossession] | None = None,
) -> list[TeamTopSlice]:
    """One TOP row per team for the resolved stat window."""
    drives = drive_possessions if drive_possessions is not None else []
    plays_by_team_week = _off_plays_by_team_week(dataset.team_env_off)

    rows: list[TeamTopSlice] = []
    for team in sorted(dataset.teams):
        method: TopMethod = "plays_share_proxy"
        share: float | None = None
        sample_games = 0

        if drives:
            share, sample_games = top_from_drive_seconds(
                drives, team=team, weeks=weeks, schedule=dataset.schedule
            )
            if share is not None:
                method = "pbp_drive"

        if share is None:
            share, sample_games = _top_from_plays_proxy(
                dataset, team=team, weeks=weeks, plays_by_team_week=plays_by_team_week
            )

        top_pct = round(share * 100.0, 1) if share is not None else None
        rows.append(
            TeamTopSlice(team=team, top_pct=top_pct, method=method, sample_games=sample_games)
        )
    return rows


def slice_to_json(row: TeamTopSlice) -> dict[str, object]:
    return {
        "team": row.team,
        "topPct": row.top_pct,
        "method": row.method,
        "sampleGames": row.sample_games,
    }
