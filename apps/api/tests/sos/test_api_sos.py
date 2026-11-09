"""HTTP tests for GET /api/v1/nfl/strength-of-schedule."""

from draft_api.main import app
from draft_api.sos.calculate import CompletedGame
from draft_api.sos.nflverse import SosDataset
from draft_api.sos.service import clear_sos_cache, set_sos_dataset_override
from fastapi.testclient import TestClient

client = TestClient(app)

TEAMS = ["AAA", "BBB", "CCC", "DDD"]


def _pts(rb: float) -> dict:
    return {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0}


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
        "AAA": {**{w: None for w in range(1, 19)}, 1: "BBB", 2: "CCC"},
        "BBB": {**{w: None for w in range(1, 19)}, 1: "AAA", 2: "DDD", 3: "CCC"},
        "CCC": {**{w: None for w in range(1, 19)}, 1: "DDD", 2: "AAA", 3: "BBB"},
        "DDD": {**{w: None for w in range(1, 19)}, 1: "CCC", 2: "BBB"},
    },
    teams=TEAMS,
)


def setup_function() -> None:
    clear_sos_cache()
    set_sos_dataset_override(FIXTURE)


def teardown_function() -> None:
    set_sos_dataset_override(None)
    clear_sos_cache()


def test_strength_of_schedule_shape():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule",
        params={
            "position": "RB",
            "metric": "fpa",
            "startWeek": 1,
            "endWeek": 3,
            "season": 2026,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["position"] == "RB"
    assert body["metric"] == "fpa"
    assert body["startWeek"] == 1
    assert body["endWeek"] == 3
    assert body["ratedThroughWeek"] == 2
    assert body["source"] == "fixture"
    assert body["stale"] is False
    assert len(body["teams"]) == 4
    assert body["teams"][0]["rank"] == 1
    assert body["teams"][0]["team"] == "CCC"
    first_weeks = body["teams"][0]["weeks"]
    assert len(first_weeks) == 18
    assert first_weeks[0]["week"] == 1
    assert "opponent" in first_weeks[0]
    assert "opponentRank" in first_weeks[0]
    assert "bye" in first_weeks[0]
    assert "inWindow" in first_weeks[0]


def test_strength_of_schedule_rejects_bad_position():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule",
        params={"position": "K", "metric": "fpa"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_position"


def test_strength_of_schedule_rejects_bad_metric():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule",
        params={"position": "RB", "metric": "epa"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_metric"


def test_strength_of_schedule_pae_metric():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule",
        params={
            "position": "RB",
            "metric": "pae",
            "startWeek": 1,
            "endWeek": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["metric"] == "pae"
