"""Committed ESPN league directory for Week D/ST league picker.

The same `{id, name}` list is the league set for
`tools/espn-mcp/scripts/export_my_rosters.py`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


class LeagueNotFoundError(LookupError):
    """Raised when leagueId is not in espn_leagues.json."""


@lru_cache(maxsize=1)
def load_espn_leagues() -> list[dict[str, str]]:
    """Return [{id, name}, ...] from packaged JSON."""
    raw = resources.files("draft_api.data").joinpath("espn_leagues.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("espn_leagues.json must be a JSON array")
    leagues: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        league_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if league_id and name:
            leagues.append({"id": league_id, "name": name})
    return leagues


def get_league(league_id: str) -> dict[str, str]:
    needle = league_id.strip()
    for league in load_espn_leagues():
        if league["id"] == needle:
            return league
    raise LeagueNotFoundError(f"Unknown ESPN league id: {league_id}")


def leagues_payload() -> dict[str, Any]:
    return {"leagues": load_espn_leagues()}
