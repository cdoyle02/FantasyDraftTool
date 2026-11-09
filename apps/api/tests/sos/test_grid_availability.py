"""SoS grid primary-player + league availability annotations."""

from __future__ import annotations

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.sos.grid_availability import annotate_grid_teams, primary_by_team


def _player(
    *,
    player_id: int,
    name: str,
    team: str,
    slot: str,
    espn_team_id: int | None,
) -> EspnRosterPlayer:
    return EspnRosterPlayer(
        player_id=player_id,
        full_name=name,
        nfl_team=team,
        roster_slot=slot,
        lineup_slot=slot,
        injury_status=None,
        espn_team_id=espn_team_id,
        availability="ONTEAM",
    )


def test_primary_by_team_keeps_first_best():
    rows = [
        {"name": "A", "team": "LAR", "opportunity": 0.9},
        {"name": "B", "team": "LAR", "opportunity": 0.1},
        {"name": "C", "team": "NE", "opportunity": 0.5},
    ]
    assert primary_by_team(rows)["LAR"]["name"] == "A"
    assert primary_by_team(rows)["NE"]["name"] == "C"


def test_annotate_available_when_not_rostered():
    teams = [{"team": "LAR", "rank": 1, "opponentAverage": 20.0, "weeks": []}]
    opportunities = [{"name": "Matthew Stafford", "team": "LAR", "opportunity": 0.8}]
    out = annotate_grid_teams(
        teams,
        position="QB",
        opportunity_players=opportunities,
        roster=[],
        owner_team_id=1,
    )
    assert out[0]["primaryPlayer"]["name"] == "Matthew Stafford"
    assert out[0]["leagueAvailability"] == "available"


def test_annotate_on_roster_vs_taken():
    teams = [
        {"team": "LAR", "rank": 1, "opponentAverage": 20.0, "weeks": []},
        {"team": "NE", "rank": 2, "opponentAverage": 18.0, "weeks": []},
    ]
    opportunities = [
        {"name": "Matthew Stafford", "team": "LAR", "opportunity": 0.8},
        {"name": "Drake Maye", "team": "NE", "opportunity": 0.7},
    ]
    roster = [
        _player(
            player_id=1,
            name="Matthew Stafford",
            team="LAR",
            slot="QB",
            espn_team_id=11,
        ),
        _player(
            player_id=2,
            name="Drake Maye",
            team="NE",
            slot="QB",
            espn_team_id=3,
        ),
    ]
    out = annotate_grid_teams(
        teams,
        position="QB",
        opportunity_players=opportunities,
        roster=roster,
        owner_team_id=11,
    )
    by_team = {row["team"]: row for row in out}
    assert by_team["LAR"]["leagueAvailability"] == "on_roster"
    assert by_team["NE"]["leagueAvailability"] == "taken"


def test_annotate_dst():
    teams = [{"team": "LAR", "rank": 1, "opponentAverage": 10.0, "weeks": []}]
    roster = [
        _player(player_id=16, name="Rams D/ST", team="LAR", slot="DST", espn_team_id=2),
    ]
    out = annotate_grid_teams(
        teams,
        position="DST",
        opportunity_players=None,
        roster=roster,
        owner_team_id=2,
    )
    assert out[0]["primaryPlayer"]["name"] == "Rams D/ST"
    assert out[0]["leagueAvailability"] == "on_roster"


def test_annotate_unknown_without_roster():
    teams = [{"team": "LAR", "rank": 1, "opponentAverage": 20.0, "weeks": []}]
    opportunities = [{"name": "Matthew Stafford", "team": "LAR", "opportunity": 0.8}]
    out = annotate_grid_teams(
        teams,
        position="QB",
        opportunity_players=opportunities,
        roster=None,
        owner_team_id=None,
    )
    assert out[0]["leagueAvailability"] == "unknown"
