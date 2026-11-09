"""HTTP tests for Workbook P2 tab routes."""

from __future__ import annotations

import json
from pathlib import Path

from draft_api.main import app, set_espn_roster_http_json
from draft_api.workbook.calculate import PassPlay, TeamRateSlice
from draft_api.workbook.nflverse import PositionalWeekRate, ScheduledGame, WorkbookDataset
from draft_api.workbook.service import (
    clear_workbook_cache,
    set_workbook_dataset_override,
    set_workbook_http_get,
)
from fastapi.testclient import TestClient

client = TestClient(app)
FIXTURES = Path(__file__).resolve().parent / "fixtures"
INJURIES_MINI = json.loads((FIXTURES / "espn_injuries_mini.json").read_text(encoding="utf-8"))

SEASON = 2026
WEEK = 10


def _fixture_dataset() -> WorkbookDataset:
    all_wr_off = {
        ("AAA", w): PositionalWeekRate(
            targets=8, receptions=5, rec_yards=50, rec_tds=1
        )
        for w in (6, 7, 8, 9)
    }
    all_wr_def = {
        ("BBB", w): PositionalWeekRate(
            targets=6, receptions=4, rec_yards=40, rec_tds=0
        )
        for w in (6, 7, 8, 9)
    }
    all_wr_def.update(
        {
            ("AAA", w): PositionalWeekRate(
                targets=5, receptions=3, rec_yards=30, rec_tds=0
            )
            for w in (6, 7, 8, 9)
        }
    )
    all_wr_off.update(
        {
            ("BBB", w): PositionalWeekRate(
                targets=7, receptions=4, rec_yards=35, rec_tds=0
            )
            for w in (6, 7, 8, 9)
        }
    )
    return WorkbookDataset(
        season=SEASON,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["AAA", "BBB"],
        schedule={w: {"AAA": "BBB", "BBB": "AAA"} for w in (6, 7, 8, 9, WEEK)},
        games=[
            ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff="2026-11-08T18:00:00Z")
        ],
        drives=[],
        pass_plays=[
            PassPlay(team="AAA", week=9, is_pass=True, xpass=0.5),
            PassPlay(team="AAA", week=9, is_pass=False, xpass=0.4),
        ],
        team_env_off=[
            TeamRateSlice(team="AAA", week=9, side="off", pass_plays=20, run_plays=15),
            TeamRateSlice(team="BBB", week=9, side="off", pass_plays=10, run_plays=15),
        ],
        team_env_def=[],
        positional_off={"all_wr": all_wr_off},
        positional_def={"all_wr": all_wr_def},
    )


def setup_function() -> None:
    clear_workbook_cache()
    set_workbook_dataset_override(_fixture_dataset())


def teardown_function() -> None:
    set_espn_roster_http_json(None)
    set_workbook_dataset_override(None)
    set_workbook_http_get(None)
    clear_workbook_cache()


def test_workbook_top_route() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/top",
        params={"week": WEEK, "window": "custom", "startWeek": 9, "endWeek": 9, "season": SEASON},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fixture"
    assert body["method"] == "plays_share_proxy"
    aaa = next(row for row in body["teams"] if row["team"] == "AAA")
    assert aaa["topPct"] == 58.3
    assert aaa["method"] == "plays_share_proxy"


def test_workbook_pace_route() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/pace",
        params={"week": WEEK, "window": "custom", "startWeek": 9, "endWeek": 9, "season": SEASON},
    )
    assert response.status_code == 200
    body = response.json()
    aaa = next(row for row in body["teams"] if row["team"] == "AAA")
    assert aaa["playsPerGame"] == 2.0


def test_workbook_injuries_route_with_fixture_http() -> None:
    def fake_http(url: str, headers: dict[str, str]) -> dict:
        return INJURIES_MINI

    set_espn_roster_http_json(fake_http)
    response = client.get(
        "/api/v1/nfl/workbook/injuries",
        params={"week": WEEK, "season": SEASON, "leagueId": "1216398267"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "espn_roster"
    assert body["inactivesAvailable"] is False
    assert len(body["injuries"]) == 3
    assert body["warnings"] == []


def test_workbook_injuries_route_unavailable_still_200() -> None:
    def boom(url: str, headers: dict[str, str]) -> dict:
        raise RuntimeError("espn down")

    set_espn_roster_http_json(boom)
    response = client.get(
        "/api/v1/nfl/workbook/injuries",
        params={"week": WEEK, "season": SEASON, "leagueId": "1216398267"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["injuries"] == []
    assert body["warnings"] == ["injuries_unavailable"]


def test_workbook_matrices_route() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/matrices/wr",
        params={
            "week": WEEK,
            "metric": "fp_per_game",
            "window": "l4",
            "scoring": "ppr",
            "season": SEASON,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["group"] == "wr"
    row = next(r for r in body["teams"] if r["team"] == "AAA")
    assert row["net"]["tier"] in {"top", "mid", "bottom"}
    assert row["net"]["tierColor"] in {"green", "neutral", "red", None}
