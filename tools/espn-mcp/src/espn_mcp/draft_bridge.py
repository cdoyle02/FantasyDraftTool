"""In-process wrappers around the draft API's weekly ESPN tools.

Each call uses the ESPN cookies for the authenticated MCP profile. Cookies are
never taken from tool arguments.
"""

from __future__ import annotations

import json
from typing import Any

from .client import EspnError
from .profiles import active_config
from .rosters import configured_leagues, select_leagues


def _league(league: str) -> dict[str, str]:
    matches = select_leagues(configured_leagues(), league)
    if len(matches) != 1:
        names = ", ".join(item["name"] for item in matches)
        raise EspnError(f"League {league!r} matched more than one league: {names}")
    return matches[0]


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def league_directory() -> str:
    return _dump({"leagues": configured_leagues()})


def kyle_dst_available(league: str) -> str:
    from draft_api.espn_available_dst import fetch_available_dst
    from draft_api.kyle_dst_available import build_kyle_available_payload
    from draft_api.main import get_kyle_dst_rankings_cached

    config = active_config()
    selected = _league(league)
    rankings = get_kyle_dst_rankings_cached()
    available = fetch_available_dst(
        league_id=selected["id"],
        season=config.season,
        espn_s2=config.espn_s2,
        swid=config.swid,
    )
    return _dump(
        build_kyle_available_payload(
            rankings_payload=rankings,
            available=available,
            league=selected,
        )
    )


def jared_k_available(league: str) -> str:
    from draft_api.espn_available_dst import fetch_available_k
    from draft_api.jared_k_available import build_jared_available_payload
    from draft_api.main import get_jared_k_rankings_cached

    config = active_config()
    selected = _league(league)
    rankings = get_jared_k_rankings_cached()
    available = fetch_available_k(
        league_id=selected["id"],
        season=config.season,
        espn_s2=config.espn_s2,
        swid=config.swid,
    )
    return _dump(
        build_jared_available_payload(
            rankings_payload=rankings,
            available=available,
            league=selected,
        )
    )


def week_odds() -> str:
    from datetime import UTC, datetime

    from draft_api.main import get_odds_provider
    from draft_api.odds import OddsApiError
    from draft_api.week_odds import build_week_odds_payload

    try:
        provider = get_odds_provider()
        return _dump(build_week_odds_payload(provider, now=datetime.now(UTC)))
    except (OddsApiError, ValueError) as exc:
        return _dump({"error": str(exc)})
