from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from espn_mcp.client import EspnConfig, EspnError, fetch
from espn_mcp.server import server


@pytest.mark.asyncio
async def test_espn_free_agents_tool_registered() -> None:
    tools = {tool.name for tool in await server.list_tools()}
    assert "espn_free_agents" in tools


@pytest.mark.asyncio
async def test_espn_free_agents_schema_has_statuses_and_sort_by() -> None:
    tool = next(item for item in await server.list_tools() if item.name == "espn_free_agents")
    schema = tool.input_schema
    assert "statuses" in schema["properties"]
    assert "sort_by" in schema["properties"]
    assert schema["properties"]["limit"]["default"] == 50


@pytest.mark.asyncio
async def test_free_agents_envelope_has_schema_version() -> None:
    from espn_mcp.server import free_agents

    payload = {
        "scoringPeriodId": 16,
        "players": [
            {
                "id": 1,
                "status": "WAIVERS",
                "onTeamId": 0,
                "player": {
                    "id": 1,
                    "fullName": "Test Player",
                    "defaultPositionId": 2,
                    "proTeamId": 1,
                    "stats": [],
                },
            }
        ],
    }

    with patch("espn_mcp.server.fetch", new=AsyncMock(return_value=payload)):
        result = json.loads(
            await free_agents(
                EspnConfig(season=2020, league_id="1", espn_s2=None, swid=None),
                "899513",
                limit=1,
                season=2020,
            )
        )

    assert result["schema_version"] == 1
    assert result["returned"] == 1
    assert result["players"][0]["is_available"] is True
    assert "fetched_at" in result


@pytest.mark.asyncio
async def test_fetch_redacts_secrets_on_http_error() -> None:
    config = EspnConfig(
        season=2020,
        league_id="1",
        espn_s2="super-secret-cookie",
        swid="{secret-swid}",
    )

    with patch("espn_mcp.client.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.side_effect = httpx.HTTPError("boom super-secret-cookie")
        client_cls.return_value = client

        with pytest.raises(EspnError, match="<redacted>") as error:
            await fetch("https://example.com", config=config)

        assert "super-secret-cookie" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "match"),
    [
        (401, "401"),
        (403, "403"),
        (404, "404"),
        (429, "429"),
    ],
)
async def test_fetch_http_status_errors(status_code: int, match: str) -> None:
    config = EspnConfig(season=2020, league_id="1", espn_s2=None, swid=None)

    response = httpx.Response(status_code, text="failure", request=httpx.Request("GET", "https://x"))

    with patch("espn_mcp.client.httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = response
        client_cls.return_value = client

        with pytest.raises(EspnError, match=match):
            await fetch("https://example.com", config=config)


@pytest.mark.asyncio
async def test_espn_league_rosters_skips_inaccessible_leagues_when_scanning_all() -> None:
    """Private leagues (e.g. Just The Tip for Katie) must not fail the whole directory scan."""
    from espn_mcp.profiles import EspnProfile, reset_profile, set_profile
    from espn_mcp.server import espn_league_rosters

    profile = EspnProfile(
        name="katie",
        token="katie-token",
        config=EspnConfig(
            season=2026,
            league_id="1216398267",
            espn_s2="katie-s2",
            swid="{katie-swid}",
        ),
    )
    token = set_profile(profile)
    leagues = [
        {"id": "1216398267", "name": "Girls Who Ball"},
        {"id": "886805", "name": "Just The Tip"},
    ]
    ok_payload = {
        "scoringPeriodId": 6,
        "members": [
            {
                "id": "{katie-swid}",
                "displayName": "Katie40890",
                "firstName": "Katie",
                "lastName": "Doyle",
            }
        ],
        "teams": [
            {
                "id": 11,
                "name": "BIG TDs",
                "abbrev": "BT",
                "primaryOwner": "{katie-swid}",
                "owners": ["{katie-swid}"],
                "record": {"overall": {"wins": 1, "losses": 0, "pointsFor": 100}},
                "roster": {"entries": []},
            }
        ],
    }

    async def fake_fetch(url: str, **kwargs: object) -> object:
        if "/leagues/" in url:
            if "/leagues/886805" in url:
                raise EspnError("ESPN returned 401. This league is private.")
            if "/leagues/1216398267" in url:
                return ok_payload
            raise AssertionError(f"unexpected league url {url}")
        # season meta (no /leagues/ segment)
        return {}

    try:
        with (
            patch("espn_mcp.server.fetch", new=AsyncMock(side_effect=fake_fetch)),
            patch("espn_mcp.rosters.configured_leagues", return_value=leagues),
        ):
            # Tool imports configured_leagues from .rosters inside the function.
            result = json.loads(await espn_league_rosters())
    finally:
        reset_profile(token)

    assert result["team_count"] == 1
    assert result["teams"][0]["team_name"] == "BIG TDs"
    assert result["skipped_leagues"] == [
        {
            "league_id": "886805",
            "league_name": "Just The Tip",
            "error": "ESPN returned 401. This league is private.",
        }
    ]


@pytest.mark.asyncio
async def test_espn_league_rosters_still_raises_for_named_inaccessible_league() -> None:
    from espn_mcp.profiles import EspnProfile, reset_profile, set_profile
    from espn_mcp.server import espn_league_rosters

    profile = EspnProfile(
        name="katie",
        token="katie-token",
        config=EspnConfig(
            season=2026,
            league_id="1216398267",
            espn_s2="katie-s2",
            swid="{katie-swid}",
        ),
    )
    token = set_profile(profile)
    leagues = [{"id": "886805", "name": "Just The Tip"}]

    async def fake_fetch(url: str, **kwargs: object) -> object:
        if "/leagues/" in url:
            raise EspnError("ESPN returned 401. This league is private.")
        return {}

    try:
        with (
            patch("espn_mcp.server.fetch", new=AsyncMock(side_effect=fake_fetch)),
            patch("espn_mcp.rosters.configured_leagues", return_value=leagues),
        ):
            with pytest.raises(EspnError, match="401"):
                await espn_league_rosters(league="Just The Tip")
    finally:
        reset_profile(token)
