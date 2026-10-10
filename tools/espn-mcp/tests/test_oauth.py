from __future__ import annotations

import json

import httpx
import pytest

from espn_mcp.client import EspnConfig
from espn_mcp.http_app import BearerProfiles
from espn_mcp.oauth import s256_challenge
from espn_mcp.profiles import EspnProfile, active_config, current_profile


@pytest.mark.asyncio
async def test_chatgpt_login_issues_an_access_token_for_michael(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "signing-secret")
    monkeypatch.setenv("MCP_LOGIN_PASSWORD", "household")
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://mcp")
    app = BearerProfiles(_echo, [_profile("michael", "michael-token", "michael-cookie")])
    transport = httpx.ASGITransport(app=app)
    verifier = "a-verifier-that-is-long-enough-for-pkce"
    challenge = s256_challenge(verifier)
    redirect_uri = "http://127.0.0.1/callback"
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp") as client:
        metadata = await client.get("/.well-known/oauth-authorization-server")
        denied = await client.post(
            "/authorize",
            data=_login("wrong", challenge, redirect_uri),
        )
        approved = await client.post(
            "/authorize",
            data=_login("household", challenge, redirect_uri),
            follow_redirects=False,
        )
        location = approved.headers["location"]
        code = location.split("code=")[1].split("&")[0]
        issued = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": "chatgpt",
                "redirect_uri": redirect_uri,
                "resource": "http://mcp/mcp",
            },
        )
        roster = await client.get(
            "/mcp",
            headers={"Authorization": f"Bearer {issued.json()['access_token']}"},
        )
        static = await client.get("/mcp", headers={"Authorization": "Bearer michael-token"})
        missing = await client.post("/mcp")

    assert metadata.json()["code_challenge_methods_supported"] == ["S256"]
    assert metadata.json()["authorization_response_iss_parameter_supported"] is True
    assert denied.status_code == 401
    assert "code=" not in denied.text
    assert approved.status_code == 302
    assert "state=abc" in location
    assert "iss=http%3A%2F%2Fmcp" in location
    assert issued.status_code == 200
    assert roster.json() == {"profile": "michael", "espn_s2": "michael-cookie"}
    assert static.json()["profile"] == "michael"
    assert 'resource_metadata="http://mcp/.well-known/oauth-protected-resource/mcp"' in (
        missing.headers["www-authenticate"]
    )


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


def _login(password: str, challenge: str, redirect_uri: str) -> dict[str, str]:
    return {
        "person": "michael",
        "password": password,
        "client_id": "chatgpt",
        "redirect_uri": redirect_uri,
        "state": "abc",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": "http://mcp/mcp",
    }
