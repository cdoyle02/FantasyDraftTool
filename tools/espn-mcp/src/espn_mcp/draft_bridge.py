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


def _trim_workbook_row(row: dict[str, Any]) -> dict[str, Any]:
    """Headline fields for chat-sized workbook_week payloads."""
    env = row.get("gameEnvironment") or {}
    return {
        "team": row.get("team"),
        "opponent": row.get("opponent"),
        "homeAway": row.get("homeAway"),
        "gameEnvironment": {
            "netDsr": env.get("netDsr"),
            "combNetDsr": env.get("combNetDsr"),
            "netDsrDiff": env.get("netDsrDiff"),
            "vegasImpliedPoints": env.get("vegasImpliedPoints"),
        },
        "qb": {"fpGTot": (row.get("qb") or {}).get("fpGTot")},
        "allWr": {"fpG": (row.get("allWr") or {}).get("fpG")},
        "outWr": {"fpG": (row.get("outWr") or {}).get("fpG")},
        "slotWr": {"fpG": (row.get("slotWr") or {}).get("fpG")},
        "te": {"fpG": (row.get("te") or {}).get("fpG")},
        "rb": {"fpGTot": (row.get("rb") or {}).get("fpGTot")},
    }


def _default_workbook_week() -> int:
    from draft_api.main import get_kyle_dst_rankings_cached

    rankings = get_kyle_dst_rankings_cached()
    week = rankings.get("week")
    if isinstance(week, int) and 1 <= week <= 18:
        return week
    return 10


def workbook_week(
    league: str,
    *,
    week: int | None = None,
    owner: str | None = None,
    window: str = "l4",
    scoring: str = "ppr",
    slate: str = "main",
    include_highlights: bool = True,
) -> str:
    """Workbook Net Matchups for one league/week with optional ESPN highlight overlay."""
    from draft_api.espn_roster import EspnRosterError, load_espn_overlay_players
    from draft_api.workbook.service import build_matchups_response

    config = active_config()
    selected = _league(league)
    resolved_week = week if week is not None else _default_workbook_week()
    warnings: list[str] = []
    owner_team_id: int | None = None

    if include_highlights and owner:
        try:
            _, _, owner_team_id = load_espn_overlay_players(
                league_id=selected["id"],
                season=config.season,
                espn_s2=config.espn_s2,
                swid=config.swid,
                owner=owner,
                include_fa=False,
            )
            if owner_team_id is None:
                warnings.append(f"owner {owner!r} did not match a team in league {selected['name']}")
        except EspnRosterError as exc:
            warnings.append(f"owner lookup failed: {exc}")

    board = build_matchups_response(
        week=resolved_week,
        window=window,
        scoring=scoring,
        slate=slate,
        season=config.season,
        league_id=selected["id"] if include_highlights else None,
        owner=owner if include_highlights and owner_team_id is None else None,
        owner_team_id=owner_team_id if include_highlights else None,
        include_fa=include_highlights,
    )

    games = [
        {
            "away": game.get("away"),
            "home": game.get("home"),
            "kickoff": game.get("kickoff"),
            "mainSlate": game.get("mainSlate"),
            "rows": [_trim_workbook_row(row) for row in (game.get("rows") or [])],
        }
        for game in board.get("games") or []
    ]

    payload: dict[str, Any] = {
        "season": board.get("season"),
        "week": board.get("week"),
        "window": board.get("window"),
        "scoring": board.get("scoring"),
        "slate": board.get("slate"),
        "ratedThroughWeek": board.get("ratedThroughWeek"),
        "source": board.get("source"),
        "stale": board.get("stale"),
        "attribution": board.get("attribution"),
        "league": selected,
        "games": games,
    }
    if include_highlights:
        payload["highlights"] = board.get("highlights") or []
        payload["joinStats"] = board.get("joinStats")
        if board.get("overlayError"):
            payload["overlayError"] = board["overlayError"]
    if warnings:
        payload["warnings"] = warnings
    return _dump(payload)
