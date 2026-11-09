"""ESPN roster overlay onto Tier 1 opportunity rows."""

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.sos.roster_join import join_roster_opportunity


def _espn_rb(*, player_id: int, name: str, team: str) -> EspnRosterPlayer:
    return EspnRosterPlayer(
        player_id=player_id,
        full_name=name,
        nfl_team=team,
        roster_slot="RB",
        lineup_slot="RB",
        injury_status=None,
        espn_team_id=7,
        availability="ONTEAM",
    )


def _opp_row(*, name: str, team: str, opportunity: float | None = 0.5) -> dict:
    return {
        "gsisId": "gsis-1",
        "playerId": None,
        "name": name,
        "team": team,
        "position": "RB",
        "week": 3,
        "opponent": "DDD",
        "opponentRank": 1,
        "softness": "soft",
        "softnessScore": 1.0,
        "usageShare": opportunity,
        "opportunity": opportunity,
        "bye": False,
    }


def test_join_matched_roster_player_gets_espn_id():
    roster = [_espn_rb(player_id=42, name="High Use", team="AAA")]
    opportunities = [_opp_row(name="High Use", team="AAA", opportunity=0.6)]
    players, stats = join_roster_opportunity(roster, opportunities, position="RB")
    assert stats["matched"] == 1
    assert stats["unmatched"] == 0
    assert len(players) == 1
    row = players[0]
    assert row["playerId"] == 42
    assert row["joinStatus"] == "matched"
    assert row["opportunity"] == 0.6
    assert row["name"] == "High Use"


def test_join_unmatched_roster_player_null_opportunity():
    roster = [_espn_rb(player_id=99, name="Unknown Back", team="BBB")]
    opportunities = [_opp_row(name="High Use", team="AAA")]
    players, stats = join_roster_opportunity(roster, opportunities, position="RB")
    assert stats["matched"] == 0
    assert stats["unmatched"] == 1
    row = players[0]
    assert row["joinStatus"] == "unmatched"
    assert row["opportunity"] is None
    assert row["playerId"] == 99


def test_join_skips_other_positions_and_sorts_by_opportunity():
    roster = [
        _espn_rb(player_id=1, name="Low Use", team="AAA"),
        EspnRosterPlayer(
            player_id=2,
            full_name="Bench WR",
            nfl_team="AAA",
            roster_slot="WR",
            lineup_slot="WR",
            injury_status=None,
            espn_team_id=7,
            availability="ONTEAM",
        ),
        _espn_rb(player_id=3, name="High Use", team="AAA"),
    ]
    opportunities = [
        _opp_row(name="Low Use", team="AAA", opportunity=0.2),
        _opp_row(name="High Use", team="AAA", opportunity=0.75),
    ]
    players, stats = join_roster_opportunity(roster, opportunities, position="RB")
    assert stats["skippedPosition"] == 1
    assert len(players) == 2
    assert players[0]["name"] == "High Use"
    assert players[1]["name"] == "Low Use"


def test_join_aliases_name_and_team():
    roster = [_espn_rb(player_id=5, name="D.J. Moore", team="WSH")]
    opportunities = [_opp_row(name="DJ Moore", team="WAS", opportunity=0.4)]
    players, stats = join_roster_opportunity(roster, opportunities, position="RB")
    assert stats["matched"] == 1
    assert players[0]["opportunity"] == 0.4
