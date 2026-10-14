"""MCP server exposing ESPN fantasy football v3 endpoints for integration work."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from mcp.server import MCPServer

from .client import (
    EspnConfig,
    EspnError,
    fetch,
    league_url,
    season_meta_url,
    season_players_url,
)
from .filters import parse_fantasy_filter
from .free_agents import (
    build_page_filter,
    effective_scoring_period,
    normalize_entries,
    scan_for_search_matches,
)
from .players import (
    normalize_player_entry,
    normalize_position_alias,
    pagination_fields,
    validate_free_agent_query,
)
from .profiles import active_config, current_profile
from .reference import (
    LINEUP_SLOT_IDS,
    POSITION_IDS,
    PRO_TEAM_IDS,
    reference_document,
)
from .shape import describe, render_json

INSTRUCTIONS = """\
Explore ESPN's undocumented fantasy football v3 API while building ESPN fantasy football
integrations. Start with espn_reference to see the endpoint and view catalog, then use
espn_request to inspect real payload shapes.

Normalized tools:
- espn_draft_picks — live/completed draft sync
- espn_league_settings — roster slots and scoring
- espn_players — draft id map (preserves availability metadata when a league is set)
- espn_free_agents — league free agents and waiver players with paging, sort, and search
- espn_transactions — waiver / add-drop / roster / trade history from mTransactions2,
  with team waiver ranks and counters

Season defaults to ESPN_SEASON (2026 when unset). League id defaults to ESPN_LEAGUE_ID.
Credentials come from the active profile (ESPN_S2 and ESPN_SWID, or Katie's pair on
her hosted login) and are never accepted as tool arguments.

Roster and show tools:
- espn_league_rosters — live rosters for every team in a configured league. Pass a
  league name or id for opponents as well as the caller. Katie's login defaults to
  her own team when no league or owner is given. Pass mine=true for the cookie owner's
  teams only.
- espn_league_directory — the configured league names and ids.
- espn_transactions — in-depth transaction and waiver log for one league (pending +
  executed), including player names when resolve_names is true.
- kyle_dst_available / jared_k_available — weekly DST and kicker rankings crossed
  with free agents in one league.
- week_odds — current-week NFL spreads and implied totals.
- ballers_latest — newest Fantasy Footballers episode summary, plus YouTube captions
  when they are published.

Girls Who Ball is Katie Doyle's league. Use owner "Katie" or her login to get her team.
"""

server: MCPServer[Any] = MCPServer(
    name="espn-fantasy",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


def _resolve(season: int | None, league_id: str | None) -> tuple[EspnConfig, str | None]:
    config = active_config()
    if season is not None:
        config = EspnConfig(
            season=season,
            league_id=config.league_id,
            espn_s2=config.espn_s2,
            swid=config.swid,
        )
    return config, league_id or config.league_id


def _require_league(league_id: str | None) -> str:
    if not league_id:
        raise EspnError(
            "No league id available. Pass league_id, or set ESPN_LEAGUE_ID in the MCP server "
            "environment. The id is the leagueId query parameter in a fantasy.espn.com URL."
        )
    return league_id


@server.tool(
    description=(
        "Endpoint paths, view parameters, id lookup tables and known gotchas for ESPN's "
        "fantasy football v3 API. No network access. Read this before calling other tools."
    )
)
def espn_reference(season: int | None = None) -> str:
    config = active_config()
    return json.dumps(reference_document(season or config.season), indent=2)


@server.tool(
    description=(
        "Call any ESPN fantasy v3 endpoint and inspect the response. Use mode='shape' "
        "(default) to see the payload structure without downloading megabytes into context, "
        "and mode='json' once you know which subtree you need."
    )
)
async def espn_request(
    views: list[str] | None = None,
    league_id: str | None = None,
    season: int | None = None,
    endpoint: Literal["league", "season_players", "season_meta"] = "league",
    scoring_period_id: int | None = None,
    fantasy_filter: dict[str, Any] | str | None = None,
    path: str | None = None,
    mode: Literal["shape", "json"] = "shape",
    depth: int = 4,
    max_chars: int = 6000,
) -> str:
    """Fetch an ESPN endpoint.

    Args:
        views: view query parameters, for example ["mDraftDetail", "mSettings"].
        league_id: ESPN league id. Defaults to ESPN_LEAGUE_ID.
        season: Season year. Defaults to ESPN_SEASON.
        endpoint: Which documented base path to use. Ignored when path is given.
        scoring_period_id: Optional scoringPeriodId query parameter.
        fantasy_filter: JSON object or JSON string sent as the X-Fantasy-Filter header.
        path: Full URL override for an endpoint not covered by the presets.
        mode: "shape" for a structural outline, "json" for the raw payload.
        depth: Nesting levels to describe in shape mode.
        max_chars: Output cap in json mode.
    """
    config, resolved_league = _resolve(season, league_id)

    if path:
        url = path
    elif endpoint == "season_players":
        url = season_players_url(config.season)
    elif endpoint == "season_meta":
        url = season_meta_url(config.season)
    else:
        url = league_url(config.season, _require_league(resolved_league))

    parsed_filter = parse_fantasy_filter(fantasy_filter)

    payload = await fetch(
        url,
        config=config,
        views=views,
        params={"scoringPeriodId": scoring_period_id},
        fantasy_filter=parsed_filter,
    )

    if mode == "shape":
        outline = {
            "url": url,
            "views": views or [],
            "season": config.season,
            "authenticated": config.authenticated,
            "shape": describe(payload, depth=depth),
        }
        return render_json(outline, max_chars)
    return render_json(payload, max_chars)


@server.tool(
    description=(
        "Normalized draft picks from view=mDraftDetail, including whether the draft is "
        "currently in progress. This is the endpoint to poll for live ESPN draft sync."
    )
)
async def espn_draft_picks(
    league_id: str | None = None,
    season: int | None = None,
    limit: int = 50,
    offset: int = 0,
    resolve_names: bool = False,
) -> str:
    """Return draft picks for a league.

    Args:
        league_id: ESPN league id. Defaults to ESPN_LEAGUE_ID.
        season: Season year. Defaults to ESPN_SEASON.
        limit: Maximum picks to return.
        offset: Pick index to start from, for paging through a completed draft.
        resolve_names: Also fetch the player universe to attach names and positions.
            This downloads a large payload, so leave it off while polling.
    """
    config, resolved_league = _resolve(season, league_id)
    return await draft_picks(
        config,
        _require_league(resolved_league),
        limit=limit,
        offset=offset,
        resolve_names=resolve_names,
    )


async def draft_picks(
    config: EspnConfig,
    league_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    resolve_names: bool = False,
) -> str:
    """Fetch and normalize a league's draft picks with an explicit configuration.

    Keeping the configuration explicit lets the public smoke test exercise the
    production normalization path without loading local environment credentials.
    """
    payload = await fetch(
        league_url(config.season, league_id),
        config=config,
        views=["mDraftDetail", "mTeam"],
    )

    detail = payload.get("draftDetail") or {}
    picks: list[dict[str, Any]] = detail.get("picks") or []

    team_names = {
        team.get("id"): team.get("name")
        or " ".join(
            filter(None, [team.get("location"), team.get("nickname")]),
        )
        or f"Team {team.get('id')}"
        for team in payload.get("teams") or []
    }

    window = picks[offset : offset + limit]
    names: dict[int, dict[str, Any]] = {}
    if resolve_names and window:
        names = await _player_lookup(config, {pick.get("playerId") for pick in window})

    normalized = []
    for pick in window:
        player_id = pick.get("playerId")
        entry: dict[str, Any] = {
            "overall_pick": pick.get("overallPickNumber"),
            "round": pick.get("roundId"),
            "round_pick": pick.get("roundPickNumber"),
            "team_id": pick.get("teamId"),
            "team_name": team_names.get(pick.get("teamId")),
            "player_id": player_id,
            "keeper": bool(pick.get("keeper")),
            "bid_amount": pick.get("bidAmount"),
            "auto_drafted": pick.get("autoDraftTypeId", 0) != 0,
        }
        if player_id in names:
            entry.update(names[player_id])
        normalized.append(entry)

    return json.dumps(
        {
            "season": config.season,
            "league_id": league_id,
            "drafted": detail.get("drafted"),
            "in_progress": detail.get("inProgress"),
            "total_picks": len(picks),
            "returned": len(normalized),
            "offset": offset,
            "picks": normalized,
            "note": (
                "Picks carry playerId only. Build an id map from espn_players, or set "
                "resolve_names=true for a one-off lookup."
            ),
        },
        indent=2,
    )


async def free_agents(
    config: EspnConfig,
    league_id: str,
    *,
    statuses: list[str] | None = None,
    position: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: Literal["percent_owned"] = "percent_owned",
    sort_asc: bool = False,
    search: str | None = None,
    scoring_period_id: int | None = None,
    season: int | None = None,
) -> str:
    """Fetch and normalize league free agents with an explicit configuration."""
    resolved_season = season if season is not None else config.season
    query = validate_free_agent_query(
        league_id=league_id,
        season=resolved_season,
        statuses=statuses,
        position=position,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_asc=sort_asc,
        scoring_period_id=scoring_period_id,
        search=search,
    )

    url = league_url(resolved_season, league_id)
    last_payload: dict[str, Any] = {}

    async def fetch_page(espn_offset: int, espn_limit: int) -> list[dict[str, Any]]:
        nonlocal last_payload
        fantasy_filter = build_page_filter(
            query,
            limit=espn_limit,
            offset=espn_offset,
        )
        payload = await fetch(
            url,
            config=config,
            views=["kona_player_info"],
            params={"scoringPeriodId": query.scoring_period_id},
            fantasy_filter=fantasy_filter,
        )
        if not isinstance(payload, dict):
            raise EspnError("ESPN response for kona_player_info must be an object")
        last_payload = payload
        players = payload.get("players")
        if players is None:
            raise EspnError("ESPN response missing players list for kona_player_info")
        return players

    search_meta: dict[str, Any] | None = None
    if query.search:
        scan = await scan_for_search_matches(fetch_page, query)
        raw_entries = scan.entries
        search_meta = {
            "query": query.search,
            "status": scan.status,
            "pages_scanned": scan.pages_scanned,
            "rows_scanned": scan.rows_scanned,
            "match_count": scan.match_count,
        }
    else:
        raw_entries = await fetch_page(query.offset, query.limit)

    effective_period = effective_scoring_period(query.scoring_period_id, last_payload)
    players = normalize_entries(
        raw_entries,
        season=resolved_season,
        effective_scoring_period=effective_period,
    )

    page = pagination_fields(offset=query.offset, limit=query.limit, returned=len(players))
    envelope: dict[str, Any] = {
        "schema_version": 1,
        "season": resolved_season,
        "league_id": league_id,
        "fetched_at": datetime.now(tz=UTC).isoformat(),
        "requested_scoring_period_id": query.scoring_period_id,
        "effective_scoring_period_id": effective_period,
        "statuses": list(query.statuses),
        "position": query.position,
        "sort_by": query.sort_by,
        "sort_asc": query.sort_asc,
        **page,
        "players": players,
    }
    if search_meta is not None:
        envelope["search"] = search_meta
    return json.dumps(envelope, indent=2)


@server.tool(
    description=(
        "Normalized league free agents and waiver players from kona_player_info with "
        "server-side status/position filters, percent-owned sort, paging, and optional "
        "multi-page name search."
    )
)
async def espn_free_agents(
    league_id: str | None = None,
    season: int | None = None,
    statuses: list[str] | None = None,
    position: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: Literal["percent_owned"] = "percent_owned",
    sort_asc: bool = False,
    search: str | None = None,
    scoring_period_id: int | None = None,
) -> str:
    """Return available players for a league.

    Args:
        league_id: ESPN league id. Defaults to ESPN_LEAGUE_ID.
        season: Season year. Defaults to ESPN_SEASON.
        statuses: Availability statuses to include. Defaults to FREEAGENT and WAIVERS.
        position: Optional QB, RB, WR, TE, K, DST, or D/ST filter applied in ESPN.
        limit: Maximum players to return (1-100).
        offset: Result offset. ESPN pool offset when unsearched; match-list offset when searched.
        sort_by: Only percent_owned is supported in Phase 1.
        sort_asc: Sort percent owned ascending when true.
        search: Case-insensitive name substring with bounded multi-page scan.
        scoring_period_id: Optional scoringPeriodId for weekly stat splits.
    """
    config, resolved_league = _resolve(season, league_id)
    return await free_agents(
        config,
        _require_league(resolved_league),
        statuses=statuses,
        position=position,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_asc=sort_asc,
        search=search,
        scoring_period_id=scoring_period_id,
        season=season,
    )


@server.tool(
    description=(
        "Normalized league configuration from view=mSettings: team count, draft type, "
        "roster slot counts and scoring format. Use this to map an ESPN league onto "
        "application league settings."
    )
)
async def espn_league_settings(
    league_id: str | None = None,
    season: int | None = None,
    include_scoring_items: bool = False,
) -> str:
    """Return league settings.

    Args:
        league_id: ESPN league id. Defaults to ESPN_LEAGUE_ID.
        season: Season year. Defaults to ESPN_SEASON.
        include_scoring_items: Include the full per-stat scoring rule list.
    """
    config, resolved_league = _resolve(season, league_id)
    payload = await fetch(
        league_url(config.season, _require_league(resolved_league)),
        config=config,
        views=["mSettings"],
    )

    settings = payload.get("settings") or {}
    roster = settings.get("rosterSettings") or {}
    draft = settings.get("draftSettings") or {}
    scoring = settings.get("scoringSettings") or {}

    slot_counts = {
        LINEUP_SLOT_IDS.get(int(slot_id), f"SLOT_{slot_id}"): count
        for slot_id, count in (roster.get("lineupSlotCounts") or {}).items()
        if count
    }

    result: dict[str, Any] = {
        "season": config.season,
        "league_id": resolved_league,
        "name": settings.get("name"),
        "team_count": settings.get("size"),
        "status": payload.get("status", {}).get("currentMatchupPeriod"),
        "draft": {
            "type": draft.get("type"),
            "time_per_selection_seconds": draft.get("timePerSelection"),
            "date": draft.get("date"),
            "keeper_count": draft.get("keeperCount"),
            "pick_order": draft.get("pickOrder"),
        },
        "roster_slots": slot_counts,
        "scoring_type": scoring.get("scoringType"),
        "reception_points": _reception_points(scoring),
    }
    if include_scoring_items:
        result["scoring_items"] = scoring.get("scoringItems")
    return json.dumps(result, indent=2)


def _reception_points(scoring: dict[str, Any]) -> float | None:
    """Extract points per reception, ESPN stat id 53."""
    for item in scoring.get("scoringItems") or []:
        if item.get("statId") == 53:
            points = item.get("points")
            if points is None:
                overrides = item.get("pointsOverrides") or {}
                points = next(iter(overrides.values()), None)
            return points
    return None


@server.tool(
    description=(
        "Player pool with ESPN player ids, positions, pro teams and optional projections. "
        "Use this to build the id map that draft picks and rosters require."
    )
)
async def espn_players(
    league_id: str | None = None,
    season: int | None = None,
    limit: int = 50,
    position: str | None = None,
    search: str | None = None,
    include_projections: bool = True,
) -> str:
    """Return a slice of the player universe.

    Args:
        league_id: ESPN league id. When omitted the public league-independent
            endpoint is used, which carries no projections or draft ranks.
        season: Season year. Defaults to ESPN_SEASON.
        limit: Maximum players to return.
        position: Filter to QB, RB, WR, TE, K or DST.
        search: Case-insensitive substring match on the player name.
        include_projections: Attach the projected season total when available.
    """
    config, resolved_league = _resolve(season, league_id)
    wanted = normalize_position_alias(position) if position else None

    if resolved_league:
        payload = await fetch(
            league_url(config.season, resolved_league),
            config=config,
            views=["kona_player_info"],
            fantasy_filter={
                "players": {
                    "limit": max(limit * 4, 200),
                    "sortDraftRanks": {
                        "sortPriority": 100,
                        "sortAsc": True,
                        "value": "PPR",
                    },
                }
            },
        )
        raw = payload.get("players") or []
    else:
        payload = await fetch(
            season_players_url(config.season),
            config=config,
            views=["players_wl"],
            params={"scoringPeriodId": 0},
        )
        raw = payload if isinstance(payload, list) else payload.get("players") or []

    results: list[dict[str, Any]] = []
    for entry in raw:
        normalized = normalize_player_entry(
            entry,
            season=config.season,
            scoring_period_id=None,
            include_legacy_projections=include_projections,
            include_full_stats=False,
        )

        name = normalized["name"]
        slot = normalized["position"]
        if wanted and slot != wanted:
            continue
        if search and search.lower() not in name.lower():
            continue

        results.append(normalized)
        if len(results) >= limit:
            break

    return json.dumps(
        {
            "season": config.season,
            "source": "kona_player_info" if resolved_league else "players_wl",
            "returned": len(results),
            "players": results,
        },
        indent=2,
    )


async def _player_lookup(config: EspnConfig, ids: set[Any]) -> dict[int, dict[str, Any]]:
    wanted = {int(value) for value in ids if value is not None}
    if not wanted:
        return {}
    # filterIds returns exactly the requested players; unfiltered players_wl is capped ~50.
    payload = await fetch(
        season_players_url(config.season),
        config=config,
        views=["players_wl"],
        params={"scoringPeriodId": 0},
        fantasy_filter={"filterIds": {"value": sorted(wanted)}},
    )
    raw = payload if isinstance(payload, list) else payload.get("players") or []
    lookup: dict[int, dict[str, Any]] = {}
    for player in raw:
        player_id = player.get("id")
        if player_id not in wanted:
            continue
        lookup[int(player_id)] = {
            "player_name": player.get("fullName"),
            "position": POSITION_IDS.get(player.get("defaultPositionId"), "UNKNOWN"),
            "pro_team": PRO_TEAM_IDS.get(player.get("proTeamId"), "UNK"),
        }
    return lookup


@server.tool(
    description=(
        "In-depth ESPN transaction and waiver history for one configured league from "
        "view=mTransactions2. Returns pending and executed waivers, add/drops, roster "
        "moves, and trades when present, with player names, team/owner context, waiver "
        "process timestamps, and per-team waiver ranks / acquisition counters."
    )
)
async def espn_transactions(
    league: str | None = None,
    owner: str | None = None,
    mine: bool | None = None,
    team_id: int | None = None,
    types: list[str] | None = None,
    statuses: list[str] | None = None,
    scoring_period_id: int | None = None,
    pending_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    resolve_names: bool = True,
    include_team_summaries: bool = True,
    season: int | None = None,
) -> str:
    """Return normalized waiver and transaction history.

    Args:
        league: League id or part of a league name. Katie defaults to Girls Who Ball.
        owner: Case-insensitive owner display/real name filter (e.g. "Katie").
        mine: When true, only the authenticated ESPN account's team activity.
        team_id: Optional ESPN team id filter.
        types: Optional WAIVER, ROSTER, TRADE, FREEAGENT, and/or DRAFT.
        statuses: Optional PENDING, EXECUTED, CANCELED, and/or FAILED.
        scoring_period_id: Limit to one fantasy week / scoring period.
        pending_only: When true, only unfinished claims / moves.
        limit: Max transactions to return (1-200).
        offset: Match-list offset after filtering/sorting newest-first.
        resolve_names: Look up player names/positions for move items.
        include_team_summaries: Include waiver ranks and season acquisition counters.
        season: Season year. Defaults to the active profile's season.
    """
    from .rosters import configured_leagues, select_leagues
    from .transactions import (
        collect_player_ids,
        normalize_transactions_payload,
        parse_status_filters,
        parse_type_filters,
    )

    config, _league_id = _resolve(season, None)
    if not config.authenticated:
        raise EspnError("ESPN cookies are not configured for this profile.")
    profile = current_profile()
    resolved_league = league
    if not resolved_league and profile is not None and profile.name == "katie":
        resolved_league = "Girls Who Ball"
    if not resolved_league:
        raise EspnError(
            "Pass league (id or name). Katie's login defaults to Girls Who Ball when omitted."
        )
    leagues = select_leagues(configured_leagues(), resolved_league)
    if len(leagues) != 1:
        names = ", ".join(item["name"] for item in leagues)
        raise EspnError(f"league must resolve to one league, got: {names}")
    item = leagues[0]
    restrict_to_owner = bool(mine)

    payload = await fetch(
        league_url(config.season, item["id"]),
        config=config,
        views=["mTransactions2", "mTeam", "mStatus"],
    )
    if not isinstance(payload, dict):
        raise EspnError(f"Unexpected ESPN payload for league {item['id']}")

    type_filters = parse_type_filters(types)
    status_filters = parse_status_filters(statuses)
    # Pre-filter without names to bound the player lookup set to the returned page.
    preview = normalize_transactions_payload(
        payload,
        league_id=item["id"],
        league_name=item["name"],
        players={},
        types=type_filters,
        statuses=status_filters,
        scoring_period_id=scoring_period_id,
        pending_only=pending_only,
        team_id=team_id,
        owner_swid=config.swid if restrict_to_owner else None,
        owner_query=owner,
        limit=limit,
        offset=offset,
        include_team_summaries=False,
    )
    players: dict[int, dict[str, Any]] = {}
    if resolve_names:
        # Look up players for the page we will return, plus any remaining filtered ids
        # when the page is small — still bounded by matched txs on this page.
        page_ids: set[int] = set()
        raw_txs = payload.get("transactions") or []
        # Recompute the same filtered window's player ids from preview rows.
        for tx in preview.get("transactions") or []:
            for move in tx.get("items") or []:
                pid = move.get("espn_player_id")
                if pid is not None:
                    page_ids.add(int(pid))
        if not page_ids:
            # Fallback: ids from raw txs that would match filters (full set can be large;
            # only used when page items somehow lack ids).
            page_ids = collect_player_ids(
                [tx for tx in raw_txs if isinstance(tx, dict)][: max(limit + offset, limit)]
            )
        players = await _player_lookup(config, page_ids)

    result = normalize_transactions_payload(
        payload,
        league_id=item["id"],
        league_name=item["name"],
        players=players,
        types=type_filters,
        statuses=status_filters,
        scoring_period_id=scoring_period_id,
        pending_only=pending_only,
        team_id=team_id,
        owner_swid=config.swid if restrict_to_owner else None,
        owner_query=owner,
        limit=limit,
        offset=offset,
        include_team_summaries=include_team_summaries,
    )
    result["profile"] = profile.name if profile is not None else "env"
    result["season"] = config.season
    return json.dumps(result, indent=2)


@server.tool(
    description=(
        "Report which credentials and defaults the server picked up from its environment, "
        "and confirm that ESPN is reachable for the configured season."
    )
)
async def espn_status() -> str:
    config = active_config()
    profile = current_profile()
    reachable: Any
    try:
        meta = await fetch(season_meta_url(config.season), config=config)
        reachable = {
            "ok": True,
            "current_scoring_period": meta.get("currentScoringPeriod", {}).get("id"),
        }
    except EspnError as error:
        reachable = {"ok": False, "error": str(error)}

    return json.dumps(
        {
            "profile": profile.name if profile is not None else "env",
            "season": config.season,
            "league_id": config.league_id,
            "cookies_present": config.authenticated,
            "espn_reachable": reachable,
        },
        indent=2,
    )


@server.tool(
    description=(
        "Live ESPN rosters for the configured leagues. Returns every team when a league "
        "or owner is given, including opponents. Omit both to list team names only, except "
        "on Katie's login, which defaults to her own team. mine=true limits the result to "
        "the authenticated ESPN account's teams. When scanning every configured league, "
        "inaccessible/private leagues are listed under skipped_leagues instead of failing "
        "the whole call."
    )
)
async def espn_league_rosters(
    league: str | None = None,
    owner: str | None = None,
    mine: bool | None = None,
    season: int | None = None,
) -> str:
    """Return compact live rosters.

    Args:
        league: League id or part of a league name. Omit to search every configured league.
        owner: Case-insensitive match on owner display name or real name, such as "Katie".
        mine: When true, only teams owned by the authenticated ESPN account.
        season: Season year. Defaults to the active profile's season.
    """
    from .rosters import (
        bye_map,
        configured_leagues,
        normalize_teams,
        resolve_roster_query,
        select_leagues,
    )

    config, _league_id = _resolve(season, None)
    if not config.authenticated:
        raise EspnError("ESPN cookies are not configured for this profile.")
    profile = current_profile()
    restrict_to_owner, include_players = resolve_roster_query(
        profile_name=profile.name if profile is not None else None,
        league=league,
        owner=owner,
        mine=mine,
    )
    leagues = select_leagues(configured_leagues(), league)
    season_meta = await fetch(
        season_meta_url(config.season),
        config=config,
        views=["proTeamSchedules_wl"],
    )
    bye_weeks = bye_map(season_meta if isinstance(season_meta, dict) else {})
    teams: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    scoring_period = None
    # When the caller names a league, failures stay hard. Across the full directory,
    # skip private/inaccessible leagues (e.g. Just The Tip for Katie, GWB for Michael)
    # the same way export_my_rosters does.
    for item in leagues:
        try:
            payload = await fetch(
                league_url(config.season, item["id"]),
                config=config,
                views=["mTeam", "mRoster", "mStatus"],
            )
        except EspnError as error:
            if league is not None:
                raise
            skipped.append(
                {
                    "league_id": item["id"],
                    "league_name": item["name"],
                    "error": str(error),
                }
            )
            continue
        if not isinstance(payload, dict):
            message = f"Unexpected ESPN payload for league {item['id']}"
            if league is not None:
                raise EspnError(message)
            skipped.append(
                {
                    "league_id": item["id"],
                    "league_name": item["name"],
                    "error": message,
                }
            )
            continue
        scoring_period = payload.get("scoringPeriodId", scoring_period)
        teams.extend(
            normalize_teams(
                payload,
                league_id=item["id"],
                league_name=item["name"],
                bye_weeks=bye_weeks,
                owner_swid=config.swid if restrict_to_owner else None,
                owner_query=owner,
                include_players=include_players,
            )
        )
    result: dict[str, Any] = {
        "profile": profile.name if profile is not None else "env",
        "season": config.season,
        "scoring_period": scoring_period,
        "include_players": include_players,
        "team_count": len(teams),
        "teams": teams,
    }
    if skipped:
        result["skipped_leagues"] = skipped
    return json.dumps(result, indent=2)


@server.tool(description="Configured ESPN league names and ids.")
def espn_league_directory() -> str:
    from .draft_bridge import league_directory

    return league_directory()


@server.tool(
    description=(
        "Kyle Krajewski weekly DST rankings crossed with FREEAGENT and WAIVERS defenses "
        "in one configured league. Uses the authenticated profile's ESPN cookies."
    )
)
def kyle_dst_available(league: str) -> str:
    """Args: league: League id or part of a league name."""
    from .draft_bridge import kyle_dst_available as _available

    return _available(league)


@server.tool(
    description=(
        "Jared Smola weekly kicker rankings crossed with FREEAGENT and WAIVERS kickers "
        "in one configured league. Uses the authenticated profile's ESPN cookies."
    )
)
def jared_k_available(league: str) -> str:
    """Args: league: League id or part of a league name."""
    from .draft_bridge import jared_k_available as _available

    return _available(league)


@server.tool(
    description="Current fantasy-week NFL spreads, totals, and ranked favorite D/ST plays."
)
def week_odds() -> str:
    from .draft_bridge import week_odds as _week_odds

    return _week_odds()


@server.tool(
    description=(
        "Newest Fantasy Footballers podcast episode: title, date, summary, and YouTube "
        "captions when the episode page publishes a video id and captions are available."
    )
)
async def ballers_latest() -> str:
    from .ballers import latest_episode

    try:
        return json.dumps(await latest_episode(), indent=2)
    except Exception as exc:  # network and parse failures stay in the tool result
        return json.dumps({"error": str(exc)})


@server.prompt(
    description="Pull Katie Doyle's current Girls Who Ball roster, including bench and IR."
)
def katie_roster() -> str:
    return (
        "Call espn_league_rosters with league 'Girls Who Ball' and owner 'Katie'. "
        "Report starters, bench, and IR with lineup slot, NFL team, injury, and fantasy points. "
        "Do not invent players that are absent from the tool result."
    )


@server.prompt(description="Pull every team's current roster in one configured ESPN league.")
def league_rosters(league: str) -> str:
    return (
        f"Call espn_league_rosters with league {league!r} and no owner filter so opponents "
        "are included. Summarize each team, then answer the user's question from those rows."
    )


@server.prompt(
    description="Read the latest Fantasy Footballers episode and compare it to a roster."
)
def ballers_and_roster(league: str = "Girls Who Ball", owner: str = "Katie") -> str:
    return (
        "Call ballers_latest, then espn_league_rosters with "
        f"league {league!r} and owner {owner!r}. "
        "Use the episode summary and transcript only when the tool returned them. "
        "Tie show notes to players actually on that roster."
    )


@server.prompt(description="Weekly DST and kicker availability for one ESPN league.")
def week_dst_k(league: str) -> str:
    return (
        f"Call kyle_dst_available and jared_k_available with league {league!r}. "
        "Also call week_odds when the question is about game script or implied totals. "
        "Recommend only defenses and kickers the tools mark available."
    )


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
