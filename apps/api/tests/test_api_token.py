"""Household API token gate (FANTASY_DRAFT_API_TOKEN)."""

from __future__ import annotations

import pytest
from draft_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure gate is off unless a test explicitly enables it."""
    monkeypatch.delenv("FANTASY_DRAFT_API_TOKEN", raising=False)


def test_gate_off_when_token_unset() -> None:
    response = client.get("/api/v1/espn/leagues")
    assert response.status_code == 200


def test_health_open_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTASY_DRAFT_API_TOKEN", "household-secret")
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/version").status_code == 200


def test_protected_route_401_without_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTASY_DRAFT_API_TOKEN", "household-secret")
    response = client.get("/api/v1/espn/leagues")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
    assert "token" in body["error"]["message"].lower()


def test_protected_route_401_with_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTASY_DRAFT_API_TOKEN", "household-secret")
    response = client.get(
        "/api/v1/espn/leagues", headers={"X-Api-Token": "wrong"}
    )
    assert response.status_code == 401


def test_protected_route_200_with_correct_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTASY_DRAFT_API_TOKEN", "household-secret")
    response = client.get(
        "/api/v1/espn/leagues", headers={"X-Api-Token": "household-secret"}
    )
    assert response.status_code == 200
    assert "leagues" in response.json()


def test_options_preflight_passes_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FANTASY_DRAFT_API_TOKEN", "household-secret")
    response = client.options(
        "/api/v1/espn/leagues",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS middleware answers preflight; auth must not 401 it.
    assert response.status_code != 401
