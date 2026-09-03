from __future__ import annotations

from typing import Any

import pytest

from espn_mcp.filters import ESPN_SCAN_PAGE_SIZE
from espn_mcp.free_agents import scan_for_search_matches
from espn_mcp.players import FreeAgentQuery, validate_free_agent_query


def _entry(name: str) -> dict[str, Any]:
    return {
        "id": hash(name) % 100000,
        "status": "WAIVERS",
        "player": {"fullName": name, "defaultPositionId": 2, "proTeamId": 1},
    }


def _page(names: list[str]) -> list[dict[str, Any]]:
    return [_entry(name) for name in names]


@pytest.mark.asyncio
async def test_search_finds_match_beyond_first_ten_with_limit_one() -> None:
    pages = {
        0: _page([f"Player {index}" for index in range(100)]),
        100: _page(["Target Smith"] + [f"Other {index}" for index in range(99)]),
    }
    requested_limits: list[int] = []

    async def fetch_page(offset: int, limit: int) -> list[dict[str, Any]]:
        requested_limits.append(limit)
        return pages.get(offset, [])

    query = validate_free_agent_query(
        league_id="899513",
        season=2020,
        statuses=["WAIVERS"],
        position=None,
        limit=1,
        offset=0,
        sort_by="percent_owned",
        sort_asc=False,
        scoring_period_id=None,
        search="smith",
    )

    result = await scan_for_search_matches(fetch_page, query)
    assert result.entries[0]["player"]["fullName"] == "Target Smith"
    assert result.status == "matched"
    assert all(size == ESPN_SCAN_PAGE_SIZE for size in requested_limits)


@pytest.mark.asyncio
async def test_search_offset_applies_to_match_list() -> None:
    pages = {
        0: _page(["Adam Smith", "Bob Smith", "Carl Smith"]),
    }

    async def fetch_page(offset: int, limit: int) -> list[dict[str, Any]]:
        return pages.get(offset, [])

    query = validate_free_agent_query(
        league_id="899513",
        season=2020,
        statuses=["WAIVERS"],
        position=None,
        limit=1,
        offset=1,
        sort_by="percent_owned",
        sort_asc=False,
        scoring_period_id=None,
        search="smith",
    )
    result = await scan_for_search_matches(fetch_page, query)
    assert result.entries[0]["player"]["fullName"] == "Bob Smith"
    assert result.match_count == 3


@pytest.mark.asyncio
async def test_search_capped_status() -> None:
    async def fetch_page(offset: int, limit: int) -> list[dict[str, Any]]:
        names = [f"NoMatch {offset + index}" for index in range(limit)]
        return _page(names)

    query = FreeAgentQuery(
        league_id="1",
        season=2020,
        statuses=("WAIVERS",),
        position=None,
        slot_ids=None,
        limit=5,
        offset=0,
        sort_by="percent_owned",
        sort_asc=False,
        search="zzznomatch",
        scoring_period_id=None,
    )
    result = await scan_for_search_matches(fetch_page, query)
    assert result.status == "capped"
    assert result.match_count == 0
