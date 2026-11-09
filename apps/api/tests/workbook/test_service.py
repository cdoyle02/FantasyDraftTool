"""Service-layer tests for Workbook matchups/feeder/explain assembly.

Mirrors the SoS service's cache/stale/dataset-override pattern, with its own
fixture dataset (no network, no FastAPI route — those land in Task 8).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from draft_api.implied_totals import GameLine
from draft_api.workbook.calculate import mean_net
from draft_api.workbook.nflverse import PositionalWeekRate, ScheduledGame, WorkbookDataset
from draft_api.workbook.service import (
    WorkbookServiceError,
    build_explain_response,
    build_feeder_response,
    build_matchups_response,
    clear_workbook_cache,
    set_workbook_dataset_override,
    set_workbook_http_get,
)

SEASON = 2026
WEEK = 10  # "this week" on the board; stats below live in weeks 1 and 6-9.


def _wr(
    *, targets: float, receptions: float, rec_yards: float, rec_tds: float
) -> PositionalWeekRate:
    return PositionalWeekRate(
        targets=targets, receptions=receptions, rec_yards=rec_yards, rec_tds=rec_tds
    )


def _fixture_dataset() -> WorkbookDataset:
    # AAA @ home, BBB @ away for the board week; plus a Monday night game
    # (CCC/DDD) to exercise the main/all slate filter.
    games = [
        ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff="2026-11-08T18:00:00Z"),
        ScheduledGame(week=WEEK, home="CCC", away="DDD", kickoff="2026-11-09T18:00:00Z"),
    ]
    schedule = {w: {"AAA": "BBB", "BBB": "AAA"} for w in (1, 6, 7, 8, 9, WEEK)}

    # AAA ALL WR offense: 8 tar / 5 rec / 50 yd / 1 TD per week, weeks 6-9 (L4).
    # Week 1 only (included in "season", excluded from "l4") is a much smaller
    # stat line so the two windows produce different fantasy points.
    all_wr_off = {("AAA", 1): _wr(targets=2, receptions=1, rec_yards=5, rec_tds=0)}
    all_wr_off.update(
        {("AAA", w): _wr(targets=8, receptions=5, rec_yards=50, rec_tds=1) for w in (6, 7, 8, 9)}
    )
    # BBB ALL WR defense allowed: 6 tar / 4 rec / 40 yd / 0 TD per week (L4),
    # plus a matching thin week-1 line.
    all_wr_def = {("BBB", 1): _wr(targets=2, receptions=1, rec_yards=5, rec_tds=0)}
    all_wr_def.update(
        {("BBB", w): _wr(targets=6, receptions=4, rec_yards=40, rec_tds=0) for w in (6, 7, 8, 9)}
    )

    # One week of Out/Slot WR OFF (AAA) + DEF (BBB) — clears Clay sample threshold.
    out_wr_off = {("AAA", 6): _wr(targets=2, receptions=1, rec_yards=20, rec_tds=0)}
    out_wr_def = {("BBB", 6): _wr(targets=2, receptions=1, rec_yards=15, rec_tds=0)}
    slot_wr_off = {("AAA", 6): _wr(targets=3, receptions=2, rec_yards=15, rec_tds=0)}
    slot_wr_def = {("BBB", 6): _wr(targets=3, receptions=2, rec_yards=10, rec_tds=0)}

    return WorkbookDataset(
        season=SEASON,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["AAA", "BBB", "CCC", "DDD"],
        schedule=schedule,
        games=games,
        drives=[],
        pass_plays=[],
        team_env_off=[],
        team_env_def=[],
        positional_off={
            "all_wr": all_wr_off,
            "out_wr": out_wr_off,
            "slot_wr": slot_wr_off,
        },
        positional_def={
            "all_wr": all_wr_def,
            "out_wr": out_wr_def,
            "slot_wr": slot_wr_def,
        },
    )


FIXTURE = _fixture_dataset()


def setup_function() -> None:
    clear_workbook_cache()
    set_workbook_dataset_override(FIXTURE)


def teardown_function() -> None:
    set_workbook_dataset_override(None)
    set_workbook_http_get(None)
    clear_workbook_cache()


def _aaa_row(body: dict) -> dict:
    game = next(g for g in body["games"] if g["home"] == "AAA")
    return next(r for r in game["rows"] if r["team"] == "AAA")


def test_matchups_response_shape_and_rated_through_week() -> None:
    body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    assert body["season"] == SEASON
    assert body["week"] == WEEK
    assert body["window"] == "l4"
    assert body["scoring"] == "ppr"
    assert body["slate"] == "all"
    assert body["ratedThroughWeek"] == WEEK - 1
    assert body["source"] == "fixture"
    assert body["stale"] is False
    assert "Majesstik/OWS Workbook" in body["attribution"]
    assert "Mike Clay" in body["attribution"]
    assert len(body["games"]) == 2  # AAA/BBB (Sunday) + CCC/DDD (Monday)

    row = _aaa_row(body)
    assert row["homeAway"] == "home"
    assert row["opponent"] == "BBB"
    assert set(row) == {
        "team",
        "homeAway",
        "opponent",
        "gameEnvironment",
        "qb",
        "allWr",
        "outWr",
        "slotWr",
        "te",
        "rb",
    }


def test_l4_window_excludes_week_one_fp_contribution() -> None:
    l4_body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    season_body = build_matchups_response(
        week=WEEK, window="season", scoring="ppr", slate="all", season=SEASON
    )

    l4_fp_g = _aaa_row(l4_body)["allWr"]["fpG"]
    season_fp_g = _aaa_row(season_body)["allWr"]["fpG"]

    # L4 (weeks 6-9 only): off 16.0 net def 8.0 -> Net 12.0.
    assert l4_fp_g == pytest.approx(12.0)
    # Season (weeks 1 + 6-9): off 13.1 net def 6.7 -> Net 9.9 (week 1 drags it down).
    assert season_fp_g == pytest.approx(9.9)
    assert l4_fp_g != season_fp_g


def test_half_ppr_lowers_wr_fp_vs_ppr() -> None:
    ppr_body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    half_body = build_matchups_response(
        week=WEEK, window="l4", scoring="half_ppr", slate="all", season=SEASON
    )

    ppr_fp_g = _aaa_row(ppr_body)["allWr"]["fpG"]
    half_fp_g = _aaa_row(half_body)["allWr"]["fpG"]

    assert ppr_fp_g == pytest.approx(12.0)
    assert half_fp_g == pytest.approx(9.75)
    assert half_fp_g < ppr_fp_g


def test_slate_main_drops_monday_night_game() -> None:
    main_body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="main", season=SEASON
    )
    all_body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )

    assert len(all_body["games"]) == 2
    assert len(main_body["games"]) == 1
    only_game = main_body["games"][0]
    assert {only_game["home"], only_game["away"]} == {"AAA", "BBB"}
    assert only_game["mainSlate"] is True

    monday_game = next(g for g in all_body["games"] if g["home"] == "CCC")
    assert monday_game["mainSlate"] is False


def _fixture_without_slot_wr() -> WorkbookDataset:
    base = _fixture_dataset()
    return replace(
        base,
        positional_off={k: v for k, v in base.positional_off.items() if k != "slot_wr"},
        positional_def={k: v for k, v in base.positional_def.items() if k != "slot_wr"},
    )


def test_slot_wr_null_with_reason_when_sample_thin() -> None:
    set_workbook_dataset_override(_fixture_without_slot_wr())
    body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    row = _aaa_row(body)
    assert row["slotWr"] == {"fpG": None, "reason": "clay_unavailable"}


def test_out_wr_computes_net_when_sample_sufficient() -> None:
    body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    row = _aaa_row(body)
    assert "reason" not in row["outWr"]
    assert row["outWr"]["fpG"] == pytest.approx(2.75)


def test_slot_wr_computes_net_when_sample_sufficient() -> None:
    body = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    row = _aaa_row(body)
    assert "reason" not in row["slotWr"]
    assert row["slotWr"]["fpG"] == pytest.approx(3.25)


def test_vegas_implied_points_null_without_odds_and_set_with_odds() -> None:
    no_odds = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    assert _aaa_row(no_odds)["gameEnvironment"]["vegasImpliedPoints"] is None

    odds_games = [
        GameLine(
            home_team="AAA",
            away_team="BBB",
            commence_time=datetime(2026, 11, 8, 18, 0, tzinfo=UTC),
            spread=-3.0,
            total=45.0,
            favorite_team="AAA",
            underdog_team="BBB",
            bookmaker="test",
        )
    ]
    with_odds = build_matchups_response(
        week=WEEK,
        window="l4",
        scoring="ppr",
        slate="all",
        season=SEASON,
        odds_games=odds_games,
    )
    game = next(g for g in with_odds["games"] if g["home"] == "AAA")
    home_row = next(r for r in game["rows"] if r["homeAway"] == "home")
    away_row = next(r for r in game["rows"] if r["homeAway"] == "away")
    assert home_row["gameEnvironment"]["vegasImpliedPoints"] == pytest.approx(24.0)
    assert away_row["gameEnvironment"]["vegasImpliedPoints"] == pytest.approx(21.0)


def test_invalid_params_raise_workbook_service_error() -> None:
    with pytest.raises(WorkbookServiceError):
        build_matchups_response(week=0, window="l4", scoring="ppr", slate="all", season=SEASON)
    with pytest.raises(WorkbookServiceError):
        build_matchups_response(
            week=WEEK, window="bogus", scoring="ppr", slate="all", season=SEASON
        )
    with pytest.raises(WorkbookServiceError):
        build_matchups_response(
            week=WEEK, window="l4", scoring="bogus", slate="all", season=SEASON
        )
    with pytest.raises(WorkbookServiceError):
        build_matchups_response(
            week=WEEK, window="l4", scoring="ppr", slate="bogus", season=SEASON
        )


def test_stale_snapshot_fallback_when_loader_fails() -> None:
    set_workbook_dataset_override(None)

    def _boom(url: str) -> bytes:
        raise RuntimeError("network down")

    set_workbook_http_get(_boom)

    # Packaged snapshot includes Clay-derived Out/Slot buckets even when live
    # nflverse is down.
    body = build_matchups_response(
        week=5,
        window="custom",
        scoring="ppr",
        slate="all",
        season=SEASON,
        custom_start_week=5,
        custom_end_week=5,
    )
    assert body["source"] == "snapshot"
    assert body["stale"] is True
    assert body["games"]
    buf_game = next(g for g in body["games"] if g["away"] == "BUF" or g["home"] == "BUF")
    buf_row = next(r for r in buf_game["rows"] if r["team"] == "BUF")
    assert buf_row["allWr"]["fpG"] is not None
    assert buf_row["outWr"]["fpG"] is not None
    assert buf_row["slotWr"]["fpG"] is not None
    assert "reason" not in buf_row["outWr"]
    assert "reason" not in buf_row["slotWr"]


def test_feeder_response_reports_off_and_def_legs() -> None:
    body = build_feeder_response(group="wr", window="l4", scoring="ppr", week=WEEK, season=SEASON)
    assert body["group"] == "wr"
    assert body["ratedThroughWeek"] == WEEK - 1

    aaa = next(row for row in body["teams"] if row["team"] == "AAA")
    bbb = next(row for row in body["teams"] if row["team"] == "BBB")
    assert aaa["off"] == pytest.approx(16.0)
    assert bbb["def"] == pytest.approx(8.0)


def test_feeder_response_rejects_unknown_group() -> None:
    with pytest.raises(WorkbookServiceError):
        build_feeder_response(group="bogus", window="l4", scoring="ppr", week=WEEK, season=SEASON)


def test_explain_slot_wr_all_none_when_clay_sample_thin() -> None:
    set_workbook_dataset_override(_fixture_without_slot_wr())
    explain = build_explain_response(
        team="AAA", week=WEEK, metric="slot_wr_fp", window="l4", scoring="ppr", season=SEASON
    )
    assert explain["off"] is None
    assert explain["def"] is None
    assert explain["net"] is None

    matchups = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    assert _aaa_row(matchups)["slotWr"] == {"fpG": None, "reason": "clay_unavailable"}


def test_explain_response_net_matches_matchups_net() -> None:
    explain = build_explain_response(
        team="AAA", week=WEEK, metric="wr_fp", window="l4", scoring="ppr", season=SEASON
    )
    assert explain["team"] == "AAA"
    assert explain["opponent"] == "BBB"
    assert explain["off"] == pytest.approx(16.0)
    assert explain["def"] == pytest.approx(8.0)
    assert explain["net"] == pytest.approx(12.0)
    assert explain["net"] == pytest.approx(mean_net(explain["off"], explain["def"]))

    matchups = build_matchups_response(
        week=WEEK, window="l4", scoring="ppr", slate="all", season=SEASON
    )
    assert explain["net"] == pytest.approx(_aaa_row(matchups)["allWr"]["fpG"])


def test_explain_response_rejects_unknown_metric() -> None:
    with pytest.raises(WorkbookServiceError):
        build_explain_response(
            team="AAA", week=WEEK, metric="bogus", window="l4", scoring="ppr", season=SEASON
        )
