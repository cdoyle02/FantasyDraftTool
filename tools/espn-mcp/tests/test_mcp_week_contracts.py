"""MCP week-contract suite: projections, actuals, FA, Katie, skips, tool surface.

These lock the behaviors we validated after the appliedStatTotal bug (stale
"points so far") and the projection-reference work. Prefer fixtures over live
ESPN so the suite stays deterministic.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from espn_mcp.client import EspnConfig, EspnError
from espn_mcp.players import normalize_player_entry
from espn_mcp.rosters import normalize_teams, resolve_roster_query
from espn_mcp.server import server


def _member(swid: str, display: str, first: str, last: str) -> dict[str, Any]:
    return {
        "id": swid,
        "displayName": display,
        "firstName": first,
        "lastName": last,
    }


def _player_entry(
    *,
    player_id: int,
    name: str,
    position_id: int,
    pro_team_id: int,
    slot_id: int,
    applied_stat_total: float,
    stats: list[dict[str, Any]],
    injury: str = "ACTIVE",
) -> dict[str, Any]:
    return {
        "lineupSlotId": slot_id,
        "playerId": player_id,
        "injuryStatus": injury,
        "playerPoolEntry": {
            "appliedStatTotal": applied_stat_total,
            "player": {
                "id": player_id,
                "fullName": name,
                "defaultPositionId": position_id,
                "proTeamId": pro_team_id,
                "injuryStatus": injury,
                "injured": injury == "OUT",
                "ownership": {"percentOwned": 50.0, "percentStarted": 20.0},
                "stats": stats,
            },
        },
    }


def _week_payload() -> dict[str, Any]:
    """Murder-Boner-shaped week 9: Henry done, Josh not started, stale applied totals."""
    return {
        "scoringPeriodId": 9,
        "members": [
            _member("{mike}", "Doyle.m", "michael", "doyle"),
            _member("{rival}", "Rival", "Riley", "Opponent"),
        ],
        "schedule": [
            {
                "matchupPeriodId": 9,
                "home": {
                    "teamId": 3,
                    "totalPoints": 0.0,
                    "totalPointsLive": 5.58,
                    "pointsByScoringPeriod": {"9": 5.58},
                    "totalProjectedPoints": 128.865,
                    "totalProjectedPointsLive": 120.393,
                },
                "away": {
                    "teamId": 7,
                    "totalPointsLive": 0.0,
                    "pointsByScoringPeriod": {"9": 0.0},
                    "totalProjectedPoints": 110.0,
                    "totalProjectedPointsLive": 110.0,
                },
            }
        ],
        "teams": [
            {
                "id": 3,
                "name": "Team Murder Boner",
                "abbrev": "mike",
                "primaryOwner": "{mike}",
                "owners": ["{mike}"],
                "record": {"overall": {"wins": 5, "losses": 3, "pointsFor": 972.14}},
                "roster": {
                    "entries": [
                        _player_entry(
                            player_id=3918298,
                            name="Josh Allen",
                            position_id=1,
                            pro_team_id=2,
                            slot_id=0,
                            applied_stat_total=26.56,
                            stats=[
                                {
                                    "seasonId": 2026,
                                    "statSourceId": 0,
                                    "statSplitTypeId": 1,
                                    "scoringPeriodId": 8,
                                    "appliedTotal": 26.56,
                                },
                                {
                                    "seasonId": 2026,
                                    "statSourceId": 1,
                                    "statSplitTypeId": 1,
                                    "scoringPeriodId": 9,
                                    "appliedTotal": 19.94,
                                },
                            ],
                        ),
                        _player_entry(
                            player_id=3043078,
                            name="Derrick Henry",
                            position_id=2,
                            pro_team_id=33,
                            slot_id=2,
                            applied_stat_total=19.58,
                            stats=[
                                {
                                    "seasonId": 2026,
                                    "statSourceId": 0,
                                    "statSplitTypeId": 1,
                                    "scoringPeriodId": 8,
                                    "appliedTotal": 14.0,
                                },
                                {
                                    "seasonId": 2026,
                                    "statSourceId": 0,
                                    "statSplitTypeId": 1,
                                    "scoringPeriodId": 9,
                                    "appliedTotal": 5.58,
                                },
                                {
                                    "seasonId": 2026,
                                    "statSourceId": 1,
                                    "statSplitTypeId": 1,
                                    "scoringPeriodId": 9,
                                    "appliedTotal": 14.05,
                                },
                            ],
                        ),
                        _player_entry(
                            player_id=99,
                            name="Zero Week Finish",
                            position_id=4,
                            pro_team_id=1,
                            slot_id=4,
                            applied_stat_total=12.0,
                            stats=[
                                {
                                    "seasonId": 2026,
                                    "statSourceId": 0,
                                    "statSplitTypeId": 1,
                                    "scoringPeriodId": 9,
                                    "appliedTotal": 0.0,
                                }
                            ],
                        ),
                    ]
                },
            },
            {
                "id": 7,
                "name": "Rival Squad",
                "abbrev": "RIV",
                "primaryOwner": "{rival}",
                "owners": ["{rival}"],
                "record": {"overall": {"wins": 4, "losses": 4, "pointsFor": 900}},
                "roster": {
                    "entries": [
                        _player_entry(
                            player_id=11,
                            name="Rival QB",
                            position_id=1,
                            pro_team_id=1,
                            slot_id=0,
                            applied_stat_total=0.0,
                            stats=[],
                        )
                    ]
                },
            },
        ],
    }


def _normalize(payload: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    defaults = {
        "league_id": "886805",
        "league_name": "Just The Tip",
        "bye_weeks": {},
        "owner_swid": None,
        "owner_query": None,
        "include_players": True,
        "season": 2026,
        "scoring_period": 9,
        "include_projections": False,
    }
    defaults.update(kwargs)
    return normalize_teams(payload, **defaults)


# --- 1. include_projections=false still exposes weekly actuals + team score ---


def test_roster_without_projections_keeps_weekly_actuals_and_team_score() -> None:
    teams = _normalize(_week_payload(), include_projections=False)
    murder = teams[0]
    by_name = {player["name"]: player for player in murder["players"]}

    assert "espn_team_projection" not in murder
    assert "espn_projection" not in by_name["Josh Allen"]
    assert murder["espn_team_score"]["espn_total_points_live"] == 5.58
    assert by_name["Josh Allen"]["weekly_actual_points"] is None
    assert by_name["Derrick Henry"]["weekly_actual_points"] == 5.58


# --- 2. Mid-week / live game: current-week actual only, not prior+current ---


def test_live_week_player_actual_is_current_week_only() -> None:
    teams = _normalize(_week_payload(), include_projections=True)
    henry = next(p for p in teams[0]["players"] if p["name"] == "Derrick Henry")
    assert henry["weekly_actual_points"] == 5.58
    assert henry["fantasy_points"] == 5.58
    assert henry["espn_projection"]["espn_projected_weekly_points"] == 14.05
    assert teams[0]["espn_team_score"]["espn_points_for_scoring_period"] == 5.58


# --- 3. True 0.0 vs null (finished duck vs not played) ---


def test_zero_actual_is_not_confused_with_not_played() -> None:
    teams = _normalize(_week_payload())
    by_name = {player["name"]: player for player in teams[0]["players"]}
    assert by_name["Zero Week Finish"]["weekly_actual_points"] == 0.0
    assert by_name["Josh Allen"]["weekly_actual_points"] is None


# --- 4. Free agents + include_projections ---


def test_free_agent_projection_flag_attaches_espn_projection() -> None:
    entry = {
        "id": 1,
        "status": "FREEAGENT",
        "onTeamId": 0,
        "player": {
            "id": 1,
            "fullName": "Available Back",
            "defaultPositionId": 2,
            "proTeamId": 1,
            "injuryStatus": "ACTIVE",
            "stats": [
                {
                    "seasonId": 2026,
                    "statSourceId": 1,
                    "statSplitTypeId": 1,
                    "scoringPeriodId": 9,
                    "appliedTotal": 8.5,
                },
                {
                    "seasonId": 2026,
                    "statSourceId": 0,
                    "statSplitTypeId": 1,
                    "scoringPeriodId": 9,
                    "appliedTotal": 3.2,
                },
            ],
        },
    }
    with_proj = normalize_player_entry(
        entry,
        season=2026,
        scoring_period_id=9,
        include_projection_reference=True,
    )
    without = normalize_player_entry(
        entry,
        season=2026,
        scoring_period_id=9,
        include_projection_reference=False,
    )
    assert with_proj["weekly_actual_points"] == 3.2
    assert with_proj["espn_projection"]["espn_projected_weekly_points"] == 8.5
    assert "espn_projection" not in without
    assert without["weekly_actual_points"] == 3.2


@pytest.mark.asyncio
async def test_free_agents_tool_include_projections_envelope() -> None:
    from espn_mcp.server import free_agents

    payload = {
        "scoringPeriodId": 9,
        "players": [
            {
                "id": 1,
                "status": "WAIVERS",
                "onTeamId": 0,
                "player": {
                    "id": 1,
                    "fullName": "Waiver Wire",
                    "defaultPositionId": 2,
                    "proTeamId": 1,
                    "stats": [
                        {
                            "seasonId": 2026,
                            "statSourceId": 1,
                            "statSplitTypeId": 1,
                            "scoringPeriodId": 9,
                            "appliedTotal": 6.1,
                        }
                    ],
                },
            }
        ],
    }
    config = EspnConfig(season=2026, league_id="1", espn_s2=None, swid=None)
    with patch("espn_mcp.server.fetch", new=AsyncMock(return_value=payload)):
        on = json.loads(
            await free_agents(config, "1", limit=1, season=2026, include_projections=True)
        )
        off = json.loads(
            await free_agents(config, "1", limit=1, season=2026, include_projections=False)
        )
    assert on["include_projections"] is True
    assert "espn_projections" in on
    assert on["players"][0]["espn_projection"]["espn_projected_weekly_points"] == 6.1
    assert off["include_projections"] is False
    assert "espn_projections" not in off
    assert "espn_projection" not in off["players"][0]


# --- 5. Katie login defaults / Girls Who Ball ---


def test_katie_login_defaults_to_her_team_only() -> None:
    restrict, include_players = resolve_roster_query(
        profile_name="katie",
        league=None,
        owner=None,
        mine=None,
    )
    assert restrict is True
    assert include_players is True


def test_katie_named_league_includes_every_team() -> None:
    restrict, include_players = resolve_roster_query(
        profile_name="katie",
        league="Girls Who Ball",
        owner=None,
        mine=None,
    )
    assert restrict is False
    assert include_players is True


# --- 6 / 7. Opponent roster when league is named; owner filter ---


def test_named_league_includes_opponent_rosters() -> None:
    teams = _normalize(_week_payload(), owner_query=None)
    assert [team["team_name"] for team in teams] == [
        "Team Murder Boner",
        "Rival Squad",
    ]


def test_owner_filter_returns_one_side_of_matchup() -> None:
    teams = _normalize(_week_payload(), owner_query="Rival")
    assert len(teams) == 1
    assert teams[0]["team_name"] == "Rival Squad"


# --- Matchup view is fetched for player rows even without projections ---


@pytest.mark.asyncio
async def test_roster_tool_requests_matchup_score_without_projections() -> None:
    from espn_mcp.profiles import EspnProfile, reset_profile, set_profile
    from espn_mcp.server import espn_league_rosters

    profile = EspnProfile(
        name="michael",
        token="mike-token",
        config=EspnConfig(
            season=2026,
            league_id="886805",
            espn_s2="mike-s2",
            swid="{mike}",
        ),
    )
    token = set_profile(profile)
    leagues = [{"id": "886805", "name": "Just The Tip"}]
    captured_views: list[list[str]] = []

    async def fake_fetch(url: str, **kwargs: object) -> object:
        views = kwargs.get("views")
        if isinstance(views, list) and "/leagues/" in url:
            captured_views.append(list(views))
            return _week_payload()
        return {}

    try:
        with (
            patch("espn_mcp.server.fetch", new=AsyncMock(side_effect=fake_fetch)),
            patch("espn_mcp.rosters.configured_leagues", return_value=leagues),
        ):
            result = json.loads(
                await espn_league_rosters(league="Just The Tip", include_projections=False)
            )
    finally:
        reset_profile(token)

    assert captured_views
    assert "mMatchupScore" in captured_views[0]
    assert result["include_projections"] is False
    assert result["teams"][0]["espn_team_score"]["espn_total_points_live"] == 5.58
    assert "espn_team_projection" not in result["teams"][0]
    josh = next(p for p in result["teams"][0]["players"] if p["name"] == "Josh Allen")
    assert josh["weekly_actual_points"] is None
    assert "espn_projection" not in josh


# --- Tool surface smoke (week tools + transactions) ---


@pytest.mark.asyncio
async def test_week_and_league_tools_are_registered() -> None:
    names = {tool.name for tool in await server.list_tools()}
    for required in {
        "espn_league_rosters",
        "espn_free_agents",
        "espn_transactions",
        "kyle_dst_available",
        "jared_k_available",
        "week_odds",
        "ballers_latest",
        "espn_league_directory",
    }:
        assert required in names


@pytest.mark.asyncio
async def test_roster_schema_exposes_include_projections() -> None:
    tool = next(item for item in await server.list_tools() if item.name == "espn_league_rosters")
    assert "include_projections" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_katie_roster_prompt_mentions_weekly_actual_points() -> None:
    prompts = {item.name: item for item in await server.list_prompts()}
    assert "katie_roster" in prompts
    # Prompt templates are rendered with empty args for no-arg prompts.
    rendered = await server.get_prompt("katie_roster")
    text = " ".join(message.content.text for message in rendered.messages if message.content.text)
    assert "weekly_actual_points" in text
    assert "fantasy points" in text.lower()
    assert "not played yet" in text.lower()


# --- Private league skip (directory scan) ---


@pytest.mark.asyncio
async def test_directory_scan_skips_private_league_for_katie() -> None:
    from espn_mcp.profiles import EspnProfile, reset_profile, set_profile
    from espn_mcp.server import espn_league_rosters

    profile = EspnProfile(
        name="katie",
        token="katie-token",
        config=EspnConfig(
            season=2026,
            league_id="1216398267",
            espn_s2="katie-s2",
            swid="{katie}",
        ),
    )
    token = set_profile(profile)
    leagues = [
        {"id": "1216398267", "name": "Girls Who Ball"},
        {"id": "886805", "name": "Just The Tip"},
    ]
    gwb = {
        "scoringPeriodId": 9,
        "members": [_member("{katie}", "Katie40890", "Katie", "Doyle")],
        "teams": [
            {
                "id": 11,
                "name": "BIG TDs",
                "abbrev": "BT",
                "primaryOwner": "{katie}",
                "owners": ["{katie}"],
                "record": {"overall": {"wins": 1, "losses": 0, "pointsFor": 100}},
                "roster": {"entries": []},
            }
        ],
        "schedule": [],
    }

    async def fake_fetch(url: str, **kwargs: object) -> object:
        if "/leagues/886805" in url:
            raise EspnError("ESPN returned 401. This league is private.")
        if "/leagues/1216398267" in url:
            return gwb
        return {}

    try:
        with (
            patch("espn_mcp.server.fetch", new=AsyncMock(side_effect=fake_fetch)),
            patch("espn_mcp.rosters.configured_leagues", return_value=leagues),
        ):
            result = json.loads(await espn_league_rosters())
    finally:
        reset_profile(token)

    assert result["teams"][0]["team_name"] == "BIG TDs"
    assert result["skipped_leagues"][0]["league_id"] == "886805"
