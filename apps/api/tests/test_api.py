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
    assert body["configuration"]["formulaVersion"] == 4
    assert body["configuration"]["oneTurnSims"] == 48
    assert body["configuration"]["simulationSeed"] == 2026
    assert body["configuration"]["formulaParams"]["sim_seed"] == 2026


def test_recommendations_endpoint_accepts_formula_v5():
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
                "formulaVersion": 5,
            },
            "draftState": {"teamCount": 2, "pickHistory": []},
            "limit": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configuration"]["formulaVersion"] == 5
    assert "negative_vorp_adjustment" in body["recommendations"][0]["breakdown"]


def test_request_validation_is_structured():
    response = client.post("/api/v1/imports/csv", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_week_odds_requires_api_key_when_no_provider_override(monkeypatch):
    from draft_api.main import set_odds_provider

    set_odds_provider(None)
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    response = client.get("/api/v1/nfl/week-odds")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "odds_unavailable"


def test_week_odds_invalid_season_week1_env_returns_503(monkeypatch):
    from datetime import datetime, timezone

    from draft_api.implied_totals import GameLine
    from draft_api.main import set_odds_provider
    from draft_api.odds.fake import FakeOddsProvider

    set_odds_provider(
        FakeOddsProvider(
            [
                GameLine(
                    home_team="KC",
                    away_team="LV",
                    commence_time=datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc),
                    spread=-7.0,
                    total=42.0,
                    favorite_team="KC",
                    underdog_team="LV",
                    bookmaker="consensus",
                )
            ]
        )
    )
    monkeypatch.setenv("NFL_SEASON_WEEK1_TUESDAY", "not-a-date")
    try:
        response = client.get("/api/v1/nfl/week-odds")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "odds_unavailable"
        assert "NFL_SEASON_WEEK1_TUESDAY" in body["error"]["message"]
    finally:
        set_odds_provider(None)


def test_week_odds_ranks_favorite_dst_by_underdog_implied(monkeypatch):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from draft_api.implied_totals import GameLine
    from draft_api.main import set_odds_provider
    from draft_api.odds.fake import FakeOddsProvider

    et = ZoneInfo("America/New_York")
    # Freeze "now" inside Week 1 (Sat Sep 12 2026 ET).
    frozen = datetime(2026, 9, 12, 12, 0, tzinfo=et)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen.replace(tzinfo=None)
            return frozen.astimezone(tz)

    monkeypatch.setattr("draft_api.main.datetime", FrozenDateTime)

    games = [
        GameLine(
            home_team="BUF",
            away_team="MIA",
            commence_time=datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc),
            spread=-3.0,
            total=48.0,
            favorite_team="BUF",
            underdog_team="MIA",
            bookmaker="consensus",
        ),
        GameLine(
            home_team="KC",
            away_team="LV",
            commence_time=datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc),
            spread=-9.5,
            total=41.5,
            favorite_team="KC",
            underdog_team="LV",
            bookmaker="consensus",
        ),
        # Outside week window (Week 2 Tuesday).
        GameLine(
            home_team="PHI",
            away_team="DAL",
            commence_time=datetime(2026, 9, 15, 17, 0, tzinfo=et),
            spread=-6.0,
            total=40.0,
            favorite_team="PHI",
            underdog_team="DAL",
            bookmaker="consensus",
        ),
    ]
    set_odds_provider(FakeOddsProvider(games))
    try:
        response = client.get("/api/v1/nfl/week-odds")
        assert response.status_code == 200
        body = response.json()
        assert body["week"] == 1
        assert [g["dstPlayTeam"] for g in body["games"]] == ["KC", "BUF"]
        assert body["games"][0]["underdogImplied"] == 16.0
        assert body["games"][1]["underdogImplied"] == 22.5
        assert all(g["dstPlayTeam"] != "PHI" for g in body["games"])
    finally:
        set_odds_provider(None)


def test_espn_leagues_endpoint():
    response = client.get("/api/v1/espn/leagues")
    assert response.status_code == 200
    body = response.json()
    assert any(league["id"] == "1216398267" for league in body["leagues"])


def test_kyle_dst_rankings_endpoint(tmp_path):
    from pathlib import Path

    from draft_api.main import set_kyle_dst_http_get

    fixture = Path(__file__).parent / "fixtures" / "kyle_dst_week1.html"
    html = fixture.read_text(encoding="utf-8")
    set_kyle_dst_http_get(lambda url: html)
    try:
        response = client.get("/api/v1/nfl/kyle-dst-rankings")
        assert response.status_code == 200
        body = response.json()
        assert body["week"] == 1
        assert body["rankings"][0]["team"] == "JAX"
    finally:
        set_kyle_dst_http_get(None)


def test_kyle_dst_available_unknown_league():
    response = client.get("/api/v1/nfl/kyle-dst-available", params={"leagueId": "999"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "league_not_found"


def test_kyle_dst_available_cross_ref():
    from pathlib import Path

    from draft_api.main import set_espn_available_http_json, set_kyle_dst_http_get

    fixture = Path(__file__).parent / "fixtures" / "kyle_dst_week1.html"
    html = fixture.read_text(encoding="utf-8")
    set_kyle_dst_http_get(lambda url: html)

    def fake_espn(url: str, headers: dict) -> dict:
        assert "1216398267" in url
        return {
            "players": [
                {
                    "status": "FREEAGENT",
                    "player": {
                        "fullName": "Jaguars D/ST",
                        "proTeamId": 30,
                        "ownership": {"percentOwned": 11.0},
                    },
                },
                {
                    "status": "WAIVERS",
                    "player": {
                        "fullName": "Titans D/ST",
                        "proTeamId": 10,
                        "ownership": {"percentOwned": 3.0},
                    },
                },
            ]
        }

    set_espn_available_http_json(fake_espn)
    try:
        response = client.get(
            "/api/v1/nfl/kyle-dst-available",
            params={"leagueId": "1216398267"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["leagueName"] == "Girls Who Ball"
        assert body["rankings"][0]["team"] == "JAX"
        assert [row["team"] for row in body["available"]] == ["JAX", "TEN"]
        assert body["available"][0]["status"] == "FREEAGENT"
    finally:
        set_kyle_dst_http_get(None)
        set_espn_available_http_json(None)


def test_jared_k_rankings_endpoint():
    from pathlib import Path

    from draft_api.main import set_jared_k_http_get

    fixture = Path(__file__).parent / "fixtures" / "jared_k_week1.html"
    html = fixture.read_text(encoding="utf-8")
    set_jared_k_http_get(lambda url: html)
    try:
        response = client.get("/api/v1/nfl/jared-k-rankings")
        assert response.status_code == 200
        body = response.json()
        assert body["week"] == 1
        assert body["rankings"][0]["player"] == "Brandon Aubrey"
        assert body["rankings"][0]["team"] == "DAL"
    finally:
        set_jared_k_http_get(None)


def test_jared_k_available_unknown_league():
    response = client.get("/api/v1/nfl/jared-k-available", params={"leagueId": "999"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "league_not_found"


def test_jared_k_available_cross_ref():
    from pathlib import Path

    from draft_api.main import set_espn_available_http_json, set_jared_k_http_get

    fixture = Path(__file__).parent / "fixtures" / "jared_k_week1.html"
    html = fixture.read_text(encoding="utf-8")
    set_jared_k_http_get(lambda url: html)

    def fake_espn(url: str, headers: dict) -> dict:
        assert "1216398267" in url
        filter_header = headers.get("X-Fantasy-Filter") or ""
        assert "17" in filter_header  # K slot
        return {
            "players": [
                {
                    "status": "FREEAGENT",
                    "player": {
                        "fullName": "Evan McPherson",
                        "proTeamId": 4,
                        "ownership": {"percentOwned": 21.6},
                    },
                },
                {
                    "status": "FREEAGENT",
                    "player": {
                        "fullName": "Jake Elliott",
                        "proTeamId": 21,
                        "ownership": {"percentOwned": 8.7},
                    },
                },
            ]
        }

    set_espn_available_http_json(fake_espn)
    try:
        response = client.get(
            "/api/v1/nfl/jared-k-available",
            params={"leagueId": "1216398267"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["leagueName"] == "Girls Who Ball"
        assert body["rankings"][0]["player"] == "Brandon Aubrey"
        assert [row["player"] for row in body["available"]] == ["Evan McPherson", "Jake Elliott"]
        assert body["available"][0]["status"] == "FREEAGENT"
    finally:
        set_jared_k_http_get(None)
        set_espn_available_http_json(None)

