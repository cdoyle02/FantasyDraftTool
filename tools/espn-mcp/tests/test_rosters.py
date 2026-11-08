from __future__ import annotations

from espn_mcp.rosters import normalize_teams, resolve_roster_query


def _payload() -> dict:
    return {
        "members": [
            {
                "id": "{katie}",
                "displayName": "Katie40890",
                "firstName": "Katie",
                "lastName": "Doyle",
            },
            {"id": "{other}", "displayName": "Rival", "firstName": "Riley", "lastName": "Opponent"},
        ],
        "teams": [
            {
                "id": 1,
                "name": "BIG TDs",
                "abbrev": "BT",
                "primaryOwner": "{katie}",
                "owners": ["{katie}"],
                "record": {"overall": {"wins": 1, "losses": 2, "pointsFor": 300.1}},
                "roster": {
                    "entries": [
                        {
                            "lineupSlotId": 0,
                            "playerPoolEntry": {
                                "appliedStatTotal": 20.4,
                                "player": {
                                    "id": 10,
                                    "fullName": "Lamar Jackson",
                                    "defaultPositionId": 1,
                                    "proTeamId": 33,
                                    "injuryStatus": "QUESTIONABLE",
                                },
                            },
                        }
                    ]
                },
            },
            {
                "id": 2,
                "name": "Other Team",
                "abbrev": "OT",
                "primaryOwner": "{other}",
                "owners": ["{other}"],
                "record": {"overall": {"wins": 3, "losses": 0, "pointsFor": 400}},
                "roster": {
                    "entries": [
                        {
                            "lineupSlotId": 2,
                            "playerPoolEntry": {
                                "appliedStatTotal": 11,
                                "player": {
                                    "id": 11,
                                    "fullName": "Rival Back",
                                    "defaultPositionId": 2,
                                    "proTeamId": 1,
                                },
                            },
                        }
                    ]
                },
            },
        ],
    }


def test_normalize_teams_includes_opponents() -> None:
    teams = normalize_teams(
        _payload(),
        league_id="1216398267",
        league_name="Girls Who Ball",
        bye_weeks={33: 13, 1: 5},
        owner_swid=None,
        owner_query=None,
        include_players=True,
    )
    assert [team["team_name"] for team in teams] == ["BIG TDs", "Other Team"]
    assert teams[1]["players"][0]["name"] == "Rival Back"


def test_owner_query_finds_katie_only() -> None:
    teams = normalize_teams(
        _payload(),
        league_id="1216398267",
        league_name="Girls Who Ball",
        bye_weeks={},
        owner_swid=None,
        owner_query="Katie",
        include_players=True,
    )
    assert len(teams) == 1
    assert teams[0]["owner_name"] == "Katie Doyle"
    assert teams[0]["players"][0]["name"] == "Lamar Jackson"
    assert "players" in teams[0]


def test_names_only_omits_player_rows() -> None:
    teams = normalize_teams(
        _payload(),
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query=None,
        include_players=False,
    )
    assert teams[0]["player_count"] == 1
    assert "players" not in teams[0]


def test_katie_login_defaults_to_her_team() -> None:
    restrict, include_players = resolve_roster_query(
        profile_name="katie",
        league=None,
        owner=None,
        mine=None,
    )
    assert restrict is True
    assert include_players is True


def test_michael_login_without_filters_is_names_only() -> None:
    restrict, include_players = resolve_roster_query(
        profile_name="michael",
        league=None,
        owner=None,
        mine=None,
    )
    assert restrict is False
    assert include_players is False


def test_roster_quotes_espn_projections_without_changing_points() -> None:
    payload = _payload()
    payload["scoringPeriodId"] = 10
    payload["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]["stats"] = [
        {
            "seasonId": 2026,
            "statSourceId": 1,
            "statSplitTypeId": 0,
            "scoringPeriodId": 0,
            "appliedTotal": 310.25,
        },
        {
            "seasonId": 2026,
            "statSourceId": 1,
            "statSplitTypeId": 1,
            "scoringPeriodId": 10,
            "appliedTotal": 18.4,
        },
        {
            "seasonId": 2026,
            "statSourceId": 0,
            "statSplitTypeId": 1,
            "scoringPeriodId": 10,
            "appliedTotal": 99,
        },
    ]
    teams = normalize_teams(
        payload,
        league_id="1216398267",
        league_name="Girls Who Ball",
        bye_weeks={},
        owner_swid=None,
        owner_query="Katie",
        include_players=True,
        season=2026,
        scoring_period=10,
        include_projections=True,
    )
    player = teams[0]["players"][0]
    # Week-10 actual from stats (99), not appliedStatTotal (20.4).
    assert player["weekly_actual_points"] == 99.0
    assert player["fantasy_points"] == 99.0
    assert player["espn_projection"] == {
        "label": "ESPN projection, reference only",
        "week": 10,
        "espn_projected_weekly_points": 18.4,
        "espn_projected_season_points": 310.25,
        "injury_status": "QUESTIONABLE",
        "team_name": "BIG TDs",
        "league_name": "Girls Who Ball",
    }
    assert "bye_week" not in player["espn_projection"]
    assert "espn_team_projection" not in teams[0]


def test_projection_zero_keeps_injury_and_hides_other_bye() -> None:
    payload = _payload()
    payload["scoringPeriodId"] = 9
    player = payload["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]
    player["injuryStatus"] = "OUT"
    player["stats"] = [
        {
            "seasonId": 2026,
            "statSourceId": 1,
            "statSplitTypeId": 1,
            "scoringPeriodId": 9,
            "appliedTotal": 0,
        }
    ]
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={33: 8},
        owner_swid=None,
        owner_query=None,
        include_players=True,
        season=2026,
        scoring_period=9,
        include_projections=True,
    )
    projection = teams[0]["players"][0]["espn_projection"]
    assert projection["espn_projected_weekly_points"] == 0.0
    assert projection["injury_status"] == "OUT"
    assert "bye_week" not in projection


def test_bye_week_is_included_only_for_this_projection_week() -> None:
    payload = _payload()
    payload["scoringPeriodId"] = 13
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={33: 13},
        owner_swid=None,
        owner_query=None,
        include_players=True,
        season=2026,
        scoring_period=13,
        include_projections=True,
    )
    assert teams[0]["players"][0]["espn_projection"]["bye_week"] == 13


def test_team_projection_is_the_matchup_total() -> None:
    payload = _payload()
    payload["scoringPeriodId"] = 9
    payload["schedule"] = [
        {
            "matchupPeriodId": 9,
            "home": {
                "teamId": 1,
                "totalProjectedPoints": 128.865,
                "totalProjectedPointsLive": 120.393,
            },
            "away": {"teamId": 2, "totalProjectedPoints": 100, "totalProjectedPointsLive": 100},
        }
    ]
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query="Katie",
        include_players=True,
        season=2026,
        scoring_period=9,
        include_projections=True,
    )
    assert teams[0]["espn_team_projection"] == {
        "label": "ESPN team projection, reference only",
        "week": 9,
        "espn_total_projected_points": 128.87,
        "espn_total_projected_points_live": 120.39,
    }


def test_roster_omits_projections_unless_requested() -> None:
    teams = normalize_teams(
        _payload(),
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query=None,
        include_players=True,
        season=2026,
        scoring_period=10,
    )
    assert "espn_projection" not in teams[0]["players"][0]
    assert "espn_team_projection" not in teams[0]


def test_explicit_league_includes_every_team_even_for_katie() -> None:
    restrict, include_players = resolve_roster_query(
        profile_name="katie",
        league="Girls Who Ball",
        owner=None,
        mine=None,
    )
    assert restrict is False
    assert include_players is True


def test_roster_weekly_actual_ignores_stale_applied_stat_total() -> None:
    """appliedStatTotal can be last week or last+this week; use the week split only."""
    payload = _payload()
    payload["scoringPeriodId"] = 9
    player = payload["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]
    # Stale/wrong ESPN roster field (Josh Allen case: still showing week 8).
    player["appliedStatTotal"] = 26.56
    player["player"]["stats"] = [
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
    ]
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query="Katie",
        include_players=True,
        season=2026,
        scoring_period=9,
    )
    row = teams[0]["players"][0]
    assert row["weekly_actual_points"] is None
    assert row["fantasy_points"] is None


def test_roster_weekly_actual_uses_current_week_stat_not_prior_sum() -> None:
    """Henry case: appliedStatTotal was week8+week9; quote week 9 only."""
    payload = _payload()
    payload["scoringPeriodId"] = 9
    player = payload["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]
    player["appliedStatTotal"] = 19.58
    player["player"]["stats"] = [
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
    ]
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query="Katie",
        include_players=True,
        season=2026,
        scoring_period=9,
    )
    row = teams[0]["players"][0]
    assert row["weekly_actual_points"] == 5.58
    assert row["fantasy_points"] == 5.58


def test_roster_weekly_actual_preserves_zero() -> None:
    payload = _payload()
    payload["scoringPeriodId"] = 9
    player = payload["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]
    player["appliedStatTotal"] = 12.0
    player["player"]["stats"] = [
        {
            "seasonId": 2026,
            "statSourceId": 0,
            "statSplitTypeId": 1,
            "scoringPeriodId": 9,
            "appliedTotal": 0.0,
        }
    ]
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query=None,
        include_players=True,
        season=2026,
        scoring_period=9,
    )
    assert teams[0]["players"][0]["weekly_actual_points"] == 0.0


def test_team_live_score_comes_from_matchup_not_player_sum() -> None:
    payload = _payload()
    payload["scoringPeriodId"] = 9
    payload["schedule"] = [
        {
            "matchupPeriodId": 9,
            "home": {
                "teamId": 1,
                "totalPoints": 0.0,
                "totalPointsLive": 5.58,
                "pointsByScoringPeriod": {"9": 5.58},
                "totalProjectedPoints": 128.865,
                "totalProjectedPointsLive": 120.393,
            },
            "away": {
                "teamId": 2,
                "totalPointsLive": 10.0,
                "pointsByScoringPeriod": {"9": 10.0},
            },
        }
    ]
    teams = normalize_teams(
        payload,
        league_id="1",
        league_name="League",
        bye_weeks={},
        owner_swid=None,
        owner_query="Katie",
        include_players=True,
        season=2026,
        scoring_period=9,
        include_projections=True,
    )
    assert teams[0]["espn_team_score"] == {
        "label": "ESPN team score, current week",
        "week": 9,
        "espn_total_points_live": 5.58,
        "espn_points_for_scoring_period": 5.58,
    }
