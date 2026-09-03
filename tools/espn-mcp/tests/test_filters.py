from __future__ import annotations

import pytest

from espn_mcp.client import EspnError
from espn_mcp.filters import (
    ESPN_SCAN_PAGE_SIZE,
    build_free_agent_filter,
    parse_fantasy_filter,
)


def test_parse_fantasy_filter_accepts_dict_without_mutation() -> None:
    original = {"players": {"limit": 5}}
    parsed = parse_fantasy_filter(original)
    assert parsed == original
    assert parsed is not original
    original["players"]["limit"] = 99
    assert parsed["players"]["limit"] == 5


def test_parse_fantasy_filter_accepts_json_string() -> None:
    assert parse_fantasy_filter('{"players":{"limit":5}}') == {"players": {"limit": 5}}


def test_parse_fantasy_filter_rejects_array() -> None:
    with pytest.raises(EspnError, match="JSON object"):
        parse_fantasy_filter("[1,2]")


def test_parse_fantasy_filter_rejects_scalar() -> None:
    with pytest.raises(EspnError, match="JSON object"):
        parse_fantasy_filter("5")


def test_parse_fantasy_filter_rejects_malformed_json() -> None:
    with pytest.raises(EspnError, match="valid JSON"):
        parse_fantasy_filter("{bad")


def test_build_free_agent_filter_default() -> None:
    filt = build_free_agent_filter(
        statuses=["FREEAGENT", "WAIVERS"],
        limit=50,
        offset=0,
        sort_by="percent_owned",
        sort_asc=False,
    )
    players = filt["players"]
    assert players["filterStatus"] == {"value": ["FREEAGENT", "WAIVERS"]}
    assert players["limit"] == 50
    assert players["offset"] == 0
    assert players["sortPercOwned"]["sortAsc"] is False


def test_build_free_agent_filter_position_slot() -> None:
    filt = build_free_agent_filter(
        statuses=["WAIVERS"],
        limit=10,
        offset=20,
        slot_ids=[16],
        sort_by="percent_owned",
        sort_asc=True,
    )
    assert filt["players"]["filterSlotIds"] == {"value": [16]}
    assert filt["players"]["sortPercOwned"]["sortAsc"] is True


def test_scan_page_size_is_verified_hundred() -> None:
    assert ESPN_SCAN_PAGE_SIZE == 100
