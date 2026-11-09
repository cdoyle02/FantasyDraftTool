"""HTTP tests for Workbook matchups ESPN overlay query params."""

import json
from datetime import UTC, datetime
from pathlib import Path

from draft_api.implied_totals import GameLine
from draft_api.main import app, set_espn_roster_http_json, set_odds_provider
from draft_api.odds.fake import FakeOddsProvider
from draft_api.workbook.nflverse import PositionalWeekRate, ScheduledGame, WorkbookDataset
from draft_api.workbook.service import (
    clear_workbook_cache,
    set_workbook_dataset_override,
)
from fastapi.testclient import TestClient

client = TestClient(app)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROSTER_MINI = json.loads((FIXTURES / "espn_roster_mini.json").read_text(encoding="utf-8"))
FA_MINI = {
    "players": [
        {
            "status": "FREEAGENT",
            "player": {
                "id": 3045147,
                "fullName": "Allen Lazard",
                "defaultPositionId": 3,
                "proTeamId": 20,
            },
        }
    ]
}

SEASON = 2026
WEEK = 10


def _fixture_dataset() -> WorkbookDataset:
    all_wr_off = {
        ("NE", w): PositionalWeekRate(targets=8, receptions=5, rec_yards=50, rec_tds=1)
        for w in (6, 7, 8, 9)
    }
    all_wr_def = {
        ("NYJ", w): PositionalWeekRate(targets=6, receptions=4, rec_yards=40, rec_tds=0)
        for w in (6, 7, 8, 9)
    }
    return WorkbookDataset(
        season=SEASON,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["NE", "NYJ"],
        schedule={w: {"NE": "NYJ", "NYJ": "NE"} for w in (6, 7, 8, 9, WEEK)},
        games=[
            ScheduledGame(week=WEEK, home="NE", away="NYJ", kickoff="2026-11-08T18:00:00Z")
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
    set_odds_provider(FakeOddsProvider(games=[]))


def teardown_function() -> None:
    set_espn_roster_http_json(None)
    set_odds_provider(None)
    set_workbook_dataset_override(None)
    clear_workbook_cache()


def test_matchups_without_league_omits_highlights() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/matchups",
        params={"week": WEEK, "slate": "all", "season": SEASON},
    )
    assert response.status_code == 200
    body = response.json()
    assert "highlights" not in body
    assert "joinStats" not in body


def test_unknown_league_returns_404() -> None:
    response = client.get(
        "/api/v1/nfl/workbook/matchups",
        params={"week": WEEK, "slate": "all", "season": SEASON, "leagueId": "not-a-league"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "league_not_found"


def test_overlay_highlights_with_fixture_http() -> None:
    roster_calls = {"n": 0}

    def fake_http(url: str, headers: dict[str, str]) -> dict:
        roster_calls["n"] += 1
        if "kona_player_info" in url:
            return FA_MINI
        return ROSTER_MINI

    set_espn_roster_http_json(fake_http)
    response = client.get(
        "/api/v1/nfl/workbook/matchups",
        params={
            "week": WEEK,
            "slate": "all",
            "season": SEASON,
            "leagueId": "1216398267",
            "owner": "Katie",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert roster_calls["n"] >= 1
    assert body["games"]
    assert body["joinStats"]["matched"] >= 1
    names = {row["displayName"] for row in body["highlights"]}
    assert "Allen Lazard" in names


def test_espn_failure_returns_empty_overlay_error() -> None:
    def boom(url: str, headers: dict[str, str]) -> dict:
        raise RuntimeError("espn down")

    set_espn_roster_http_json(boom)
    response = client.get(
        "/api/v1/nfl/workbook/matchups",
        params={
            "week": WEEK,
            "slate": "all",
            "season": SEASON,
            "leagueId": "1216398267",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["highlights"] == []
    assert body["overlayError"] == "espn_unavailable"
