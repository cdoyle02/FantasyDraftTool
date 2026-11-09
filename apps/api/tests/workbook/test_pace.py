"""Pace tab plays per game aggregates."""

from __future__ import annotations

import pytest
from draft_api.workbook.calculate import PassPlay
from draft_api.workbook.nflverse import WorkbookDataset
from draft_api.workbook.pace import CountablePlay, build_pace_table, offensive_plays_per_game

WEEK = 5


def test_offensive_plays_per_game_excludes_play_type() -> None:
    plays = [
        CountablePlay(team="KC", week=WEEK, is_pass=True),
        CountablePlay(team="KC", week=WEEK, is_pass=False),
        CountablePlay(team="KC", week=WEEK, is_pass=False, play_type="kneel"),
        CountablePlay(team="KC", week=WEEK + 1, is_pass=True),
    ]
    plays_pg, pass_rate, run_rate = offensive_plays_per_game(plays, team="KC", weeks={WEEK, WEEK + 1})
    assert plays_pg == pytest.approx(1.5)
    assert pass_rate == pytest.approx(2 / 3)
    assert run_rate == pytest.approx(1 / 3)


def test_build_pace_table_from_pass_plays() -> None:
    dataset = WorkbookDataset(
        season=2026,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["KC", "BUF"],
        schedule={WEEK: {"KC": "BUF", "BUF": "KC"}},
        games=[],
        drives=[],
        pass_plays=[
            PassPlay(team="KC", week=WEEK, is_pass=True, xpass=0.5),
            PassPlay(team="KC", week=WEEK, is_pass=False, xpass=0.4),
            PassPlay(team="KC", week=WEEK, is_pass=True, xpass=0.6),
            PassPlay(team="KC", week=WEEK, is_pass=False, xpass=0.4),
        ],
        team_env_off=[],
        team_env_def=[],
        positional_off={},
        positional_def={},
    )
    rows = build_pace_table(dataset, weeks={WEEK})
    kc = next(row for row in rows if row.team == "KC")
    assert kc.plays_per_game == pytest.approx(4.0)
    assert kc.pass_rate == pytest.approx(0.5)
