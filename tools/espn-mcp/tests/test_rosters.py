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


def test_explicit_league_includes_every_team_even_for_katie() -> None:
    restrict, include_players = resolve_roster_query(
        profile_name="katie",
        league="Girls Who Ball",
        owner=None,
        mine=None,
    )
    assert restrict is False
    assert include_players is True
