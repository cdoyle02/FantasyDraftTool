"""MCP server exposing ESPN fantasy football v3 endpoints for integration work."""

from __future__ import annotations

import json
from typing import Any, Literal

from mcp.server import MCPServer

from .client import (
    EspnConfig,
    EspnError,
    fetch,
    league_url,
    load_config,
    season_meta_url,
    season_players_url,
)
from .reference import (
    LINEUP_SLOT_IDS,
    POSITION_IDS,
    PRO_TEAM_IDS,
    reference_document,
    stat_source_ids,
)
from .shape import describe, render_json

INSTRUCTIONS = """\
Explore ESPN's undocumented fantasy football v3 API while building an ESPN draft
integration. Start with espn_reference to see the endpoint and view catalog, then use
espn_request to inspect real payload shapes. espn_draft_picks, espn_league_settings and
espn_players return normalized output suited to mapping into an application domain model.

Season defaults to ESPN_SEASON (2026 when unset). League id defaults to ESPN_LEAGUE_ID.
Credentials come from ESPN_S2 and ESPN_SWID and are never accepted as tool arguments.
"""

server: MCPServer[Any] = MCPServer(
    name="espn-fantasy",
    version="0.1.0",
    instructions=INSTRUCTIONS,
)


def _resolve(season: int | None, league_id: str | None) -> tuple[EspnConfig, str | None]:
    config = load_config()
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
    config = load_config()
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
    fantasy_filter: str | None = None,
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
        fantasy_filter: JSON string sent as the X-Fantasy-Filter header.
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

    parsed_filter: dict[str, Any] | None = None
    if fantasy_filter:
        try:
            parsed_filter = json.loads(fantasy_filter)
        except json.JSONDecodeError as error:
            raise EspnError(f"fantasy_filter must be valid JSON: {error}") from error

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
    payload = await fetch(
        league_url(config.season, _require_league(resolved_league)),
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
            "league_id": resolved_league,
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
    wanted = position.upper() if position else None

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
        raw = [entry.get("player", entry) for entry in payload.get("players") or []]
    else:
        payload = await fetch(
            season_players_url(config.season),
            config=config,
            views=["players_wl"],
            params={"scoringPeriodId": 0},
        )
        raw = payload if isinstance(payload, list) else payload.get("players") or []

    projected_id = stat_source_ids(config.season)["projected_season"]
    results: list[dict[str, Any]] = []
    for player in raw:
        name = player.get("fullName") or player.get("name") or ""
        slot = POSITION_IDS.get(player.get("defaultPositionId"), "UNKNOWN")
        if wanted and slot != wanted:
            continue
        if search and search.lower() not in name.lower():
            continue

        entry: dict[str, Any] = {
            "player_id": player.get("id"),
            "name": name,
            "position": slot,
            "pro_team": PRO_TEAM_IDS.get(player.get("proTeamId"), "UNK"),
            "injury_status": player.get("injuryStatus"),
        }
        if include_projections:
            entry["projected_points"] = _projected_total(player, projected_id)
            ranks = player.get("draftRanksByRankType") or {}
            entry["ppr_draft_rank"] = (ranks.get("PPR") or {}).get("rank")
        results.append(entry)
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


def _projected_total(player: dict[str, Any], projected_id: str) -> float | None:
    for stat in player.get("stats") or []:
        if stat.get("id") == projected_id or (
            stat.get("statSourceId") == 1 and stat.get("statSplitTypeId") == 0
        ):
            return stat.get("appliedTotal")
    return None


async def _player_lookup(config: EspnConfig, ids: set[Any]) -> dict[int, dict[str, Any]]:
    payload = await fetch(
        season_players_url(config.season),
        config=config,
        views=["players_wl"],
        params={"scoringPeriodId": 0},
    )
    raw = payload if isinstance(payload, list) else payload.get("players") or []
    wanted = {value for value in ids if value is not None}
    lookup: dict[int, dict[str, Any]] = {}
    for player in raw:
        if player.get("id") in wanted:
            lookup[player["id"]] = {
                "player_name": player.get("fullName"),
                "position": POSITION_IDS.get(player.get("defaultPositionId"), "UNKNOWN"),
                "pro_team": PRO_TEAM_IDS.get(player.get("proTeamId"), "UNK"),
            }
    return lookup


@server.tool(
    description=(
        "Report which credentials and defaults the server picked up from its environment, "
        "and confirm that ESPN is reachable for the configured season."
    )
)
async def espn_status() -> str:
    config = load_config()
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
            "season": config.season,
            "league_id": config.league_id,
            "cookies_present": config.authenticated,
            "espn_reachable": reachable,
        },
        indent=2,
    )


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
