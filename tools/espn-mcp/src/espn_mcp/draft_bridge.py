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


def _normalize_sos_position(position: str) -> str:
    key = position.strip().upper()
    if key in {"D/ST", "DEF", "D"}:
        return "DST"
    return key


def _trim_sos_week_cell(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "week": cell.get("week"),
        "opponent": cell.get("opponent"),
        "rank": cell.get("rank"),
        "softness": cell.get("softness"),
        "bye": cell.get("bye"),
        "inWindow": cell.get("inWindow"),
        "shrunkAfpa": cell.get("shrunkAfpa"),
        "shrunkEpa": cell.get("shrunkEpa"),
    }


def _trim_sos_team_row(row: dict[str, Any], *, from_week: int | None) -> dict[str, Any]:
    weeks = row.get("weeks") or []
    if from_week is not None:
        weeks = [w for w in weeks if isinstance(w.get("week"), int) and w["week"] >= from_week]
    return {
        "team": row.get("team"),
        "rank": row.get("rank"),
        "opponentAverage": row.get("opponentAverage"),
        "primaryPlayer": row.get("primaryPlayer"),
        "leagueAvailability": row.get("leagueAvailability"),
        "weeks": [_trim_sos_week_cell(w) for w in weeks],
    }


def _trim_sos_opportunity_player(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": row.get("name"),
        "team": row.get("team"),
        "position": row.get("position"),
        "week": row.get("week"),
        "opponent": row.get("opponent"),
        "opponentRank": row.get("opponentRank"),
        "softness": row.get("softness"),
        "usageShare": row.get("usageShare"),
        "opportunity": row.get("opportunity"),
        "bye": row.get("bye"),
        "joinStatus": row.get("joinStatus"),
        "lineupSlot": row.get("lineupSlot"),
        "injuryStatus": row.get("injuryStatus"),
        "gameScriptApplied": row.get("gameScriptApplied"),
        "snapFiltered": row.get("snapFiltered"),
    }


def sos_grid(
    league: str,
    position: str,
    *,
    tier: int = 1,
    window: str = "l8",
    wr_role: str = "all",
    from_week: int | None = None,
) -> str:
    """Tier 1/2 SoS team grid with optional league FA/Mine/Taken availability."""
    from draft_api.sos.clay_roles import parse_wr_role
    from draft_api.sos.service import (
        build_tier1_strength_of_schedule_response,
        build_tier2_strength_of_schedule_response,
    )

    config = active_config()
    selected = _league(league)
    position_key = _normalize_sos_position(position)
    window_key = window.strip().lower()
    if window_key not in {"l4", "l8", "season"}:
        raise EspnError(f"window must be l4, l8, or season (got {window!r})")
    if tier not in {1, 2}:
        raise EspnError(f"tier must be 1 or 2 (got {tier!r})")

    try:
        role = parse_wr_role(wr_role)
    except ValueError as exc:
        raise EspnError(str(exc)) from exc

    if tier == 1:
        if position_key not in {"QB", "RB", "WR", "TE", "DST"}:
            raise EspnError(f"Tier 1 position must be QB, RB, WR, TE, or DST (got {position!r})")
        board = build_tier1_strength_of_schedule_response(
            position=position_key,  # type: ignore[arg-type]
            window=window_key,  # type: ignore[arg-type]
            season=config.season,
            wr_role=role,
            league_id=selected["id"],
        )
    else:
        if position_key not in {"QB", "RB", "WR", "TE"}:
            raise EspnError(f"Tier 2 position must be QB, RB, WR, or TE (got {position!r})")
        board = build_tier2_strength_of_schedule_response(
            position=position_key,  # type: ignore[arg-type]
            window=window_key,  # type: ignore[arg-type]
            season=config.season,
            wr_role=role,
            league_id=selected["id"],
        )

    rated = board.get("ratedThroughWeek")
    start = from_week
    if start is None and isinstance(rated, int):
        start = min(18, max(1, rated + 1))

    payload: dict[str, Any] = {
        "tier": tier,
        "season": board.get("season"),
        "position": board.get("position"),
        "window": board.get("window"),
        "startWeek": board.get("startWeek"),
        "endWeek": board.get("endWeek"),
        "ratedThroughWeek": rated,
        "ratingWeeks": board.get("ratingWeeks"),
        "shrinkK": board.get("shrinkK"),
        "source": board.get("source"),
        "stale": board.get("stale"),
        "fetchedAt": board.get("fetchedAt"),
        "wrRole": board.get("wrRole", role if role != "all" else None),
        "league": selected,
        "leagueId": board.get("leagueId"),
        "leagueName": board.get("leagueName"),
        "fromWeek": start,
        "teams": [_trim_sos_team_row(row, from_week=start) for row in board.get("teams") or []],
    }
    # Drop null wrRole for cleaner chat payloads.
    if payload["wrRole"] is None:
        del payload["wrRole"]
    return _dump(payload)


def sos_opportunity(
    league: str,
    position: str,
    *,
    tier: int = 1,
    week: int | None = None,
    window: str = "l8",
    wr_role: str = "all",
    top_n: int = 40,
) -> str:
    """Tier 1/2 SoS opportunity list joined to one league's rosters."""
    from draft_api.sos.clay_roles import parse_wr_role
    from draft_api.sos.service import (
        build_tier1_opportunity_response,
        build_tier2_opportunity_response,
    )

    config = active_config()
    selected = _league(league)
    position_key = _normalize_sos_position(position)
    window_key = window.strip().lower()
    if window_key not in {"l4", "l8", "season"}:
        raise EspnError(f"window must be l4, l8, or season (got {window!r})")
    if tier not in {1, 2}:
        raise EspnError(f"tier must be 1 or 2 (got {tier!r})")
    if position_key not in {"QB", "RB", "WR", "TE"}:
        raise EspnError(f"opportunity position must be QB, RB, WR, or TE (got {position!r})")
    if top_n < 1 or top_n > 200:
        raise EspnError(f"top_n must be 1–200 (got {top_n!r})")

    try:
        role = parse_wr_role(wr_role)
    except ValueError as exc:
        raise EspnError(str(exc)) from exc

    resolved_week = week if week is not None else _default_workbook_week()
    if tier == 1:
        board = build_tier1_opportunity_response(
            position=position_key,  # type: ignore[arg-type]
            window=window_key,  # type: ignore[arg-type]
            week=resolved_week,
            season=config.season,
            league_id=selected["id"],
            wr_role=role,
        )
    else:
        board = build_tier2_opportunity_response(
            position=position_key,  # type: ignore[arg-type]
            window=window_key,  # type: ignore[arg-type]
            week=resolved_week,
            season=config.season,
            league_id=selected["id"],
            wr_role=role,
        )

    players = [_trim_sos_opportunity_player(p) for p in (board.get("players") or [])[:top_n]]
    payload: dict[str, Any] = {
        "tier": tier,
        "season": board.get("season"),
        "position": board.get("position"),
        "window": board.get("window"),
        "week": board.get("week"),
        "ratedThroughWeek": board.get("ratedThroughWeek"),
        "ratingWeeks": board.get("ratingWeeks"),
        "source": board.get("source"),
        "stale": board.get("stale"),
        "fetchedAt": board.get("fetchedAt"),
        "wrRole": board.get("wrRole", role if role != "all" else None),
        "league": selected,
        "leagueId": board.get("leagueId"),
        "leagueName": board.get("leagueName"),
        "joinStats": board.get("joinStats"),
        "players": players,
        "playerCount": len(board.get("players") or []),
        "returned": len(players),
    }
    if board.get("overlayError"):
        payload["overlayError"] = board["overlayError"]
    if board.get("usageUnavailable"):
        payload["usageUnavailable"] = True
    if payload["wrRole"] is None:
        del payload["wrRole"]
    return _dump(payload)


def clay_shadow_week(*, week: int | None = None) -> str:
    """Mike Clay WR↔CB shadow cheatsheet for the board week."""
    from draft_api.workbook.service import build_clay_shadow_response

    config = active_config()
    resolved_week = week if week is not None else _default_workbook_week()
    payload = build_clay_shadow_response(week=resolved_week, season=config.season)
    return _dump(payload)


def player_intel(
    name: str,
    *,
    league: str | None = None,
    week: int | None = None,
    team: str | None = None,
) -> str:
    """Compose injury / Net / Clay role+shadow feeds for one player."""
    from draft_api.workbook.service import build_player_intel_response

    config = active_config()
    resolved_week = week if week is not None else _default_workbook_week()
    league_id: str | None = None
    if league:
        league_id = _league(league)["id"]
    payload = build_player_intel_response(
        name=name,
        week=resolved_week,
        team=team,
        league_id=league_id,
        season=config.season,
    )
    return _dump(payload)
