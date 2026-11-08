"""Workbook matchup Net row helpers."""

import pytest
from draft_api.workbook.calculate import (
    TeamRateSlice,
    build_game_environment_net,
    build_positional_net,
    build_team_env_rates,
    is_main_slate,
    resolve_stat_weeks,
)


def test_game_environment_net_averages_offense_and_opposing_defense() -> None:
    weeks = resolve_stat_weeks(
        mode="l4", rated_through_week=8, custom_start=None, custom_end=None
    )
    assert weeks == {5, 6, 7, 8}

    slices = [
        TeamRateSlice(
            team="KC",
            week=5,
            side="off",
            proe=4.0,
            pass_plays=36.0,
            epa_pass=0.12,
            xplsv_pass=0.16,
            run_plays=24.0,
            epa_run=0.02,
            xplsv_run=0.08,
        ),
        TeamRateSlice(
            team="KC",
            week=6,
            side="off",
            proe=8.0,
            pass_plays=40.0,
            epa_pass=0.18,
            xplsv_pass=0.20,
            run_plays=28.0,
            epa_run=0.04,
            xplsv_run=0.10,
        ),
        TeamRateSlice(
            team="BUF",
            week=5,
            side="def",
            proe=2.0,
            pass_plays=30.0,
            epa_pass=-0.02,
            xplsv_pass=0.10,
            run_plays=20.0,
            epa_run=-0.04,
            xplsv_run=0.04,
        ),
        TeamRateSlice(
            team="BUF",
            week=6,
            side="def",
            proe=6.0,
            pass_plays=34.0,
            epa_pass=0.06,
            xplsv_pass=0.12,
            run_plays=22.0,
            epa_run=0.00,
            xplsv_run=0.06,
        ),
        TeamRateSlice(
            team="KC",
            week=4,
            side="off",
            proe=100.0,
        ),
    ]
    team_off = build_team_env_rates(slices, team="KC", side="off", weeks=weeks)
    opp_def = build_team_env_rates(slices, team="BUF", side="def", weeks=weeks)

    row = build_game_environment_net(
        team_off=team_off,
        opp_def=opp_def,
        team_net_dsr=0.62,
        opp_net_dsr=0.54,
        implied_points=26.5,
    )

    assert row == pytest.approx(
        {
            "netDsr": 0.62,
            "combNetDsr": 0.58,
            "netDsrDiff": 0.08,
            "netProe": 5.0,
            "netPassPlays": 35.0,
            "netEpaPass": 0.085,
            "netXplsvPass": 0.145,
            "netRunPlays": 23.5,
            "netEpaRun": 0.005,
            "netXplsvRun": 0.07,
            "vegasImpliedPoints": 26.5,
        }
    )


def test_positional_net_averages_each_metric_key() -> None:
    off: dict[str, float | None] = {"wr": 18.0, "slot": 12.0, "te": None}
    opp_def: dict[str, float | None] = {"wr": 14.0, "slot": 20.0, "te": 8.0}

    assert build_positional_net(off, opp_def) == {
        "wr": 16.0,
        "slot": 16.0,
        "te": None,
    }


def test_resolve_stat_weeks_modes_and_custom_clipping() -> None:
    assert resolve_stat_weeks(
        mode="season", rated_through_week=3, custom_start=None, custom_end=None
    ) == {1, 2, 3}
    assert resolve_stat_weeks(
        mode="custom", rated_through_week=8, custom_start=-3, custom_end=20
    ) == set(range(1, 19))
    assert resolve_stat_weeks(
        mode="l4", rated_through_week=2, custom_start=None, custom_end=None
    ) == {1, 2}


def test_main_slate_is_sunday_before_chicago_7pm_only() -> None:
    assert is_main_slate(weekday_local=6, kickoff_hour_local=12) is True
    assert is_main_slate(weekday_local=0, kickoff_hour_local=12) is False
    assert is_main_slate(weekday_local=6, kickoff_hour_local=19) is False
