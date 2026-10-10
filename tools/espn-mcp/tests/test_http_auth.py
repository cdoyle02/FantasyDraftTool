from __future__ import annotations

import json

import httpx
import pytest

from espn_mcp.client import EspnConfig
from espn_mcp.http_app import BearerProfiles, create_app
from espn_mcp.profiles import EspnProfile, active_config, current_profile


def _profile(name: str, token: str, cookie: str) -> EspnProfile:
    return EspnProfile(
        name=name,
        token=token,
        config=EspnConfig(season=2026, league_id=None, espn_s2=cookie, swid=f"{{{name}}}"),
    )


async def _echo(scope, receive, send):
    del receive
    if scope["type"] != "http":
        return
    profile = current_profile()
    body = json.dumps(
        {
            "profile": profile.name if profile else None,
            "espn_s2": active_config().espn_s2,
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


@pytest.mark.asyncio
async def test_katie_token_uses_only_her_cookies() -> None:
    app = BearerProfiles(
        _echo,
        [
            _profile("michael", "michael-token", "michael-cookie"),
            _profile("katie", "katie-token", "katie-cookie"),
        ],
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp") as client:
        katie = await client.get("/mcp", headers={"Authorization": "Bearer katie-token"})
        michael = await client.get("/mcp", headers={"Authorization": "Bearer michael-token"})
        rejected = await client.get("/mcp", headers={"Authorization": "Bearer nope"})

    assert katie.json() == {"profile": "katie", "espn_s2": "katie-cookie"}
    assert michael.json() == {"profile": "michael", "espn_s2": "michael-cookie"}
    assert rejected.status_code == 401
    assert rejected.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_katie_token_without_cookies_is_unconfigured() -> None:
    unconfigured = EspnProfile(
        name="katie",
        token="katie-token",
        config=EspnConfig(season=2026, league_id=None, espn_s2=None, swid=None),
    )
    app = BearerProfiles(
        _echo,
        [_profile("michael", "michael-token", "michael-cookie"), unconfigured],
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp") as client:
        response = await client.get("/mcp", headers={"Authorization": "Bearer katie-token"})
    assert response.status_code == 401
    assert response.json()["error"] == "profile_unconfigured"


@pytest.mark.asyncio
async def test_health_is_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "michael-token")
    monkeypatch.setenv("ESPN_S2", "michael-cookie")
    monkeypatch.setenv("ESPN_SWID", "{michael}")
    monkeypatch.setenv("MCP_AUTH_TOKEN_KATIE", "katie-token")
    monkeypatch.delenv("ESPN_S2_KATIE", raising=False)
    monkeypatch.delenv("ESPN_SWID_KATIE", raising=False)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp") as client:
        health = await client.get("/health")
        blocked = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert blocked.status_code == 401
