"""TOP tab pure functions and table assembly."""

from __future__ import annotations

import pytest
from draft_api.workbook.calculate import TeamRateSlice
from draft_api.workbook.nflverse import ScheduledGame, WorkbookDataset
from draft_api.workbook.top import (
    DrivePossession,
    build_top_table,
    top_from_drive_seconds,
    top_plays_share_proxy,
)

WEEK = 9


def test_top_plays_share_proxy_one_game() -> None:
    assert top_plays_share_proxy(35, 25) == pytest.approx(35 / 60)
    assert top_plays_share_proxy(35, 25) * 100 == pytest.approx(58.3333333, rel=1e-4)


def test_build_top_table_proxy_from_team_env() -> None:
    dataset = WorkbookDataset(
        season=2026,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["AAA", "BBB"],
        schedule={WEEK: {"AAA": "BBB", "BBB": "AAA"}},
        games=[ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff=None)],
        drives=[],
        pass_plays=[],
        team_env_off=[
            TeamRateSlice(team="AAA", week=WEEK, side="off", pass_plays=20, run_plays=15),
            TeamRateSlice(team="BBB", week=WEEK, side="off", pass_plays=10, run_plays=15),
        ],
        team_env_def=[],
        positional_off={},
        positional_def={},
    )

    rows = build_top_table(dataset, weeks={WEEK})
    aaa = next(row for row in rows if row.team == "AAA")
    bbb = next(row for row in rows if row.team == "BBB")
    assert aaa.method == "plays_share_proxy"
    assert aaa.top_pct == pytest.approx(58.3)
    assert aaa.sample_games == 1
    assert bbb.top_pct == pytest.approx(41.7)
    assert bbb.sample_games == 1


def test_top_from_drive_seconds_when_pbp_present() -> None:
    drives = [
        DrivePossession(team="AAA", week=WEEK, seconds=300),
        DrivePossession(team="BBB", week=WEEK, seconds=200),
    ]
    schedule = {WEEK: {"AAA": "BBB", "BBB": "AAA"}}
    share, games = top_from_drive_seconds(drives, team="AAA", weeks={WEEK}, schedule=schedule)
    assert games == 1
    assert share == pytest.approx(0.6)
