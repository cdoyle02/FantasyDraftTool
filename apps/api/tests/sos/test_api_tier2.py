"""HTTP tests for GET /api/v1/nfl/strength-of-schedule/tier2."""

from draft_api.main import app
from draft_api.sos.calculate import CompletedGame
from draft_api.sos.nflverse import SosDataset
from draft_api.sos.service import (
    clear_sos_cache,
    set_sos_dataset_override,
    set_sos_snap_rows_override,
    set_sos_stats_rows_override,
)
from fastapi.testclient import TestClient

client = TestClient(app)

TEAMS = ["AAA", "BBB"]


def _pts(rb: float) -> dict:
    return {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0, "DST": 0.0}


FIXTURE = SosDataset(
    season=2026,
    fetched_at="2026-11-08T12:00:00Z",
    games=[
        CompletedGame(week=1, offense="AAA", defense="BBB", points=_pts(10)),
        CompletedGame(week=1, offense="BBB", defense="AAA", points=_pts(8)),
    ],
    schedule={
        "AAA": {**{w: None for w in range(1, 19)}, 1: "BBB", 2: "BBB"},
        "BBB": {**{w: None for w in range(1, 19)}, 1: "AAA", 2: "AAA"},
    },
    teams=TEAMS,
)

EPA_STATS = [
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "opponent_team": "BBB",
        "player_id": "R1",
        "player_display_name": "Back",
        "carries": "10",
        "rushing_epa": "6",
    }
]


def setup_function() -> None:
    clear_sos_cache()
    set_sos_dataset_override(FIXTURE)
    set_sos_stats_rows_override(EPA_STATS)


def teardown_function() -> None:
    set_sos_dataset_override(None)
    set_sos_stats_rows_override(None)
    set_sos_snap_rows_override(None)
    clear_sos_cache()


def test_tier2_grid_returns_shrunk_epa_cells():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier2",
        params={"position": "RB", "startWeek": 1, "endWeek": 2, "season": 2026},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["softnessMetric"] == "epa_allowed"
    cell = body["teams"][0]["weeks"][0]
    assert "shrunkEpa" in cell
    assert "softness" in cell


def test_tier2_rejects_wr_position():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier2",
        params={"position": "WR", "season": 2026},
    )
    assert response.status_code == 400


def test_tier2_opportunity_metadata():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier2/opportunity",
        params={"position": "RB", "week": 2, "season": 2026},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["minOffenseSnapPct"] == 0.2
    assert "snapFiltered" in body
    assert body["softnessMetric"] == "epa_allowed"
