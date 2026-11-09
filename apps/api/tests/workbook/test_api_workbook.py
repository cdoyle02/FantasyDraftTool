"""HTTP tests for GET /api/v1/nfl/workbook/* routes."""

from draft_api.main import app
from draft_api.workbook.nflverse import PositionalWeekRate, ScheduledGame, WorkbookDataset
from draft_api.workbook.service import (
    clear_workbook_cache,
    set_workbook_dataset_override,
    set_workbook_http_get,
)
from fastapi.testclient import TestClient

client = TestClient(app)

SEASON = 2026
WEEK = 10


def _wr(
    *, targets: float, receptions: float, rec_yards: float, rec_tds: float
) -> PositionalWeekRate:
    return PositionalWeekRate(
        targets=targets, receptions=receptions, rec_yards=rec_yards, rec_tds=rec_tds
    )


def _fixture_dataset() -> WorkbookDataset:
    all_wr_off = {
        ("AAA", w): _wr(targets=8, receptions=5, rec_yards=50, rec_tds=1)
        for w in (6, 7, 8, 9)
    }
    all_wr_def = {
        ("BBB", w): _wr(targets=6, receptions=4, rec_yards=40, rec_tds=0)
        for w in (6, 7, 8, 9)
    }
    return WorkbookDataset(
        season=SEASON,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["AAA", "BBB"],
        schedule={w: {"AAA": "BBB", "BBB": "AAA"} for w in (6, 7, 8, 9, WEEK)},
        games=[
            ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff="2026-11-08T18:00:00Z")
        ],
        drives=[],
        pass_plays=[],
        team_env_off=[],
        team_env_def=[],
        positional_off={"all_wr": all_wr_off},
        positional_def={"all_wr": all_wr_def},
    )


def setup_function() -> None:
    clear_workbook_cache()
    set_workbook_dataset_override(_fixture_dataset())


def teardown_function() -> None:
    set_workbook_dataset_override(None)
    set_workbook_http_get(None)
    clear_workbook_cache()


def test_workbook_matchups_route_returns_board() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/matchups",
        params={
            "week": WEEK,
            "window": "l4",
            "scoring": "ppr",
            "slate": "all",
            "season": SEASON,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fixture"
    assert body["week"] == WEEK
    assert body["games"][0]["home"] == "AAA"
    row = next(row for row in body["games"][0]["rows"] if row["team"] == "AAA")
    assert row["allWr"]["fpG"] == 12.0


def test_workbook_feeders_route_returns_group_table() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/feeders/wr",
        params={"week": WEEK, "window": "l4", "scoring": "ppr", "season": SEASON},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["group"] == "wr"
    aaa = next(row for row in body["teams"] if row["team"] == "AAA")
    assert aaa["off"] == 16.0


def test_workbook_explain_route_returns_metric_breakdown() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/explain",
        params={
            "team": "AAA",
            "week": WEEK,
            "metric": "wr_fp",
            "window": "l4",
            "scoring": "ppr",
            "season": SEASON,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["team"] == "AAA"
    assert body["opponent"] == "BBB"
    assert body["net"] == 12.0


def test_workbook_routes_reject_invalid_params() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/feeders/not-a-group",
        params={"week": WEEK, "window": "l4", "scoring": "ppr", "season": SEASON},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_params"


def test_workbook_routes_report_unavailable_dataset() -> None:
    set_workbook_dataset_override(None)

    def _boom(url: str) -> bytes:
        raise RuntimeError(f"offline: {url}")

    set_workbook_http_get(_boom)

    response = client.get(
        "/api/v1/nfl/workbook/matchups",
        params={
            "week": WEEK,
            "window": "l4",
            "scoring": "ppr",
            "slate": "all",
            "season": 2099,
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "workbook_unavailable"
