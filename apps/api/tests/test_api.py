from draft_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_and_version():
    assert client.get("/health").json() == {"status": "ok"}
    version = client.get("/api/v1/version")
    assert version.status_code == 200
    assert version.json() == {"api": "0.1.0", "engine": "0.1.0"}


def test_csv_import_success_keeps_adjustments_separate():
    response = client.post(
        "/api/v1/imports/csv",
        json={
            "content": "Player,Team,POS,FPTS,ADP,Tier\nPlayer One,AAA,RB,250,10,1\n"
        },
    )

    assert response.status_code == 200
    assert response.json()["players"][0]["position"] == "RB"
    assert response.json()["adjustments"] == []


def test_csv_import_returns_structured_error():
    response = client.post(
        "/api/v1/imports/csv",
        json={"content": "Player,POS,FPTS\nBad Player,NOPE,abc\n"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "csv_import_error"
    assert len(body["error"]["details"]) == 1


def test_recommendations_endpoint():
    response = client.post(
        "/api/v1/recommendations",
        json={
            "players": [
                {
                    "id": "rb-1",
                    "name": "Running Back",
                    "position": "RB",
                    "projectedPoints": 250,
                    "adp": 10,
                    "tier": 1,
                },
                {
                    "id": "rb-2",
                    "name": "Replacement Back",
                    "position": "RB",
                    "projectedPoints": 150,
                    "adp": 50,
                    "tier": 2,
                },
            ],
            "settings": {
                "teamCount": 2,
                "rosterSlots": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "BENCH": 1},
                "userTeamId": "1",
            },
            "draftState": {"teamCount": 2, "pickHistory": []},
            "limit": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["recommendations"][0]["player_id"] == "rb-1"
    assert "breakdown" in body["recommendations"][0]


def test_request_validation_is_structured():
    response = client.post("/api/v1/imports/csv", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
