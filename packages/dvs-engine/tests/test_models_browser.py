import json

import pytest
from dvs_engine import LeagueSettings, Player, Position, recommendation_json


def test_domain_validation():
    with pytest.raises(ValueError, match="tier"):
        Player("id", "Name", Position.RB, tier=0)
    with pytest.raises(ValueError, match="team_count"):
        LeagueSettings(team_count=1)


def test_browser_json_entrypoint(players, settings):
    payload = {
        "players": [
            {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "projectedPoints": player.projected_points,
                "adp": player.adp,
                "tier": player.tier,
            }
            for player in players
        ],
        "settings": {
            "teamCount": settings.team_count,
            "rosterSlots": settings.roster_slots,
            "userTeamId": "1",
        },
        "draftState": {"teamCount": settings.team_count, "pickHistory": []},
        "adjustments": [{"playerId": "qb-1", "pointsDelta": 5, "tag": "myGuy"}],
        "limit": 3,
    }
    output = json.loads(recommendation_json(json.dumps(payload)))

    assert len(output["recommendations"]) == 3
    assert {"player_id", "dvs_score", "breakdown", "tier_label"} <= output[
        "recommendations"
    ][0].keys()
    assert output["configuration"]["formulaVersion"] == 4
    assert output["configuration"]["oneTurnSims"] == 48
    assert output["configuration"]["simulationSeed"] == 2026
    assert output["configuration"]["formulaParams"]["one_turn_sims"] == 48


def test_browser_json_excludes_reserved_rosters_without_advancing_pick(players, settings):
    reserved_id = players[0].id
    payload = {
        "players": [
            {
                "id": player.id,
                "name": player.name,
                "position": player.position,
                "projectedPoints": player.projected_points,
                "adp": player.adp,
                "tier": player.tier,
            }
            for player in players
        ],
        "settings": {
            "teamCount": settings.team_count,
            "rosterSlots": settings.roster_slots,
            "userTeamId": "1",
            "formulaVersion": 4,
        },
        "draftState": {
            "teamCount": settings.team_count,
            "pickHistory": [],
            "reservedRosters": {"6": [reserved_id]},
        },
        "adjustments": [],
        "limit": 20,
    }
    output = json.loads(recommendation_json(json.dumps(payload)))
    assert all(
        item["player_id"] != reserved_id for item in output["recommendations"]
    )
