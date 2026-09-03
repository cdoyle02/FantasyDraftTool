"""X-Fantasy-Filter construction and parsing for ESPN kona_player_info requests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .client import EspnError

# Live-verified maximum ESPN page size for kona_player_info availability queries.
ESPN_SCAN_PAGE_SIZE = 100
SEARCH_ROW_CAP = 500

POSITION_FILTER_SLOTS: dict[str, int] = {
    "QB": 0,
    "RB": 2,
    "WR": 4,
    "TE": 6,
    "K": 17,
    "DST": 16,
}

SORT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "percent_owned": {"sortPercOwned": {"sortPriority": 1, "sortAsc": False}},
}

DEFAULT_AVAILABILITY_STATUSES = ("FREEAGENT", "WAIVERS")


def parse_fantasy_filter(value: dict[str, Any] | str | None) -> dict[str, Any] | None:
    """Parse a tool-supplied fantasy filter into a dict for the HTTP client."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise EspnError(f"fantasy_filter must be valid JSON: {error}") from error
    elif isinstance(value, Mapping):
        parsed = deepcopy(dict(value))
    else:
        raise EspnError(
            f"fantasy_filter must be a JSON object or JSON string, got {type(value).__name__}"
        )
    if not isinstance(parsed, dict):
        raise EspnError("fantasy_filter must decode to a JSON object, not an array or scalar")
    return parsed


def build_free_agent_filter(
    *,
    statuses: list[str],
    limit: int,
    offset: int,
    slot_ids: list[int] | None = None,
    sort_by: str = "percent_owned",
    sort_asc: bool = False,
) -> dict[str, Any]:
    """Build a verified X-Fantasy-Filter payload for league available-player queries."""
    if sort_by not in SORT_DEFINITIONS:
        raise EspnError(f"Unsupported sort_by {sort_by!r}")

    sort_block = dict(SORT_DEFINITIONS[sort_by])
    sort_key = next(iter(sort_block))
    sort_block[sort_key] = {**sort_block[sort_key], "sortAsc": sort_asc}

    players: dict[str, Any] = {
        "filterStatus": {"value": list(statuses)},
        "limit": limit,
        "offset": offset,
        **sort_block,
    }
    if slot_ids:
        players["filterSlotIds"] = {"value": list(slot_ids)}
    return {"players": players}
