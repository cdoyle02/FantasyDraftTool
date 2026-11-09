"""HTTP tests for GET /api/v1/nfl/strength-of-schedule/tier1."""

from unittest.mock import patch

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.main import app, set_espn_roster_http_json
from draft_api.sos.calculate import CompletedGame
from draft_api.sos.nflverse import SosDataset
from draft_api.sos.service import (
    clear_sos_cache,
    set_sos_dataset_override,
    set_sos_stats_rows_override,
)
from fastapi.testclient import TestClient

client = TestClient(app)

TEAMS = ["AAA", "BBB", "CCC", "DDD"]


def _pts(rb: float) -> dict:
    return {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0, "DST": 0.0}


FIXTURE = SosDataset(
    season=2026,
    fetched_at="2026-11-08T12:00:00Z",
    games=[
        CompletedGame(week=1, offense="AAA", defense="BBB", points=_pts(20)),
        CompletedGame(week=1, offense="BBB", defense="AAA", points=_pts(10)),
        CompletedGame(week=1, offense="CCC", defense="DDD", points=_pts(30)),
        CompletedGame(week=1, offense="DDD", defense="CCC", points=_pts(0)),
        CompletedGame(week=2, offense="AAA", defense="CCC", points=_pts(14)),
        CompletedGame(week=2, offense="CCC", defense="AAA", points=_pts(16)),
        CompletedGame(week=2, offense="BBB", defense="DDD", points=_pts(12)),
        CompletedGame(week=2, offense="DDD", defense="BBB", points=_pts(8)),
    ],
    schedule={
        "AAA": {**{w: None for w in range(1, 19)}, 1: "BBB", 2: "CCC", 3: "DDD"},
        "BBB": {**{w: None for w in range(1, 19)}, 1: "AAA", 2: "DDD", 3: "CCC"},
        "CCC": {**{w: None for w in range(1, 19)}, 1: "DDD", 2: "AAA", 3: "BBB"},
        "DDD": {**{w: None for w in range(1, 19)}, 1: "CCC", 2: "BBB", 3: "AAA"},
    },
    teams=TEAMS,
)


def setup_function() -> None:
    clear_sos_cache()
    set_sos_dataset_override(FIXTURE)


STATS_ROWS = [
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB1",
        "player_display_name": "Workhorse",
        "carries": "20",
    },
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB2",
        "player_display_name": "Change",
        "carries": "5",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB1",
        "player_display_name": "Workhorse",
        "carries": "18",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB2",
        "player_display_name": "Change",
        "carries": "6",
    },
]


def teardown_function() -> None:
    set_sos_dataset_override(None)
    set_sos_stats_rows_override(None)
    set_espn_roster_http_json(None)
    clear_sos_cache()


def test_tier1_defaults_to_l8_window_param():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1",
        params={"position": "RB", "startWeek": 1, "endWeek": 3, "season": 2026},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "l8"
    assert body["shrinkK"] == 4
    assert body["ratedThroughWeek"] == 2
    assert len(body["teams"]) == 4
    cell = body["teams"][0]["weeks"][0]
    assert "shrunkAfpa" in cell
    assert "softness" in cell
    assert "softnessScore" in cell


def test_tier1_window_season_toggle():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1",
        params={"position": "RB", "window": "season", "startWeek": 1, "endWeek": 2},
    )
    assert response.status_code == 200
    assert response.json()["window"] == "season"
    assert response.json()["ratingWeeks"] == [1, 2]


def test_tier1_opportunity_returns_players():
    set_sos_stats_rows_override(STATS_ROWS)
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1/opportunity",
        params={"position": "RB", "window": "season", "week": 3, "season": 2026},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "season"
    assert body["week"] == 3
    assert body["shrinkK"] == 4
    assert len(body["players"]) >= 1
    player = body["players"][0]
    assert "opportunity" in player
    assert "usageShare" in player
    assert "softnessScore" in player


def test_tier1_opportunity_rejects_dst():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1/opportunity",
        params={"position": "DST"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_position"


def test_tier1_opportunity_unknown_league_404():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1/opportunity",
        params={"position": "RB", "leagueId": "12345"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "league_not_found"


@patch("draft_api.sos.service.fetch_league_roster")
def test_tier1_opportunity_league_roster_join(mock_fetch):
    set_sos_stats_rows_override(STATS_ROWS)
    mock_fetch.return_value = [
        EspnRosterPlayer(
            player_id=9001,
            full_name="Workhorse",
            nfl_team="AAA",
            roster_slot="RB",
            lineup_slot="RB",
            injury_status=None,
            espn_team_id=7,
            availability="ONTEAM",
        )
    ]
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1/opportunity",
        params={
            "position": "RB",
            "window": "season",
            "week": 3,
            "season": 2026,
            "leagueId": "1216398267",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["leagueId"] == "1216398267"
    assert body["joinStats"]["matched"] >= 1
    workhorse = next(p for p in body["players"] if p["playerId"] == 9001)
    assert workhorse["joinStatus"] == "matched"
    assert workhorse["opportunity"] is not None


def test_tier1_rejects_bad_window():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier1",
        params={"position": "RB", "window": "l12"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_window"
