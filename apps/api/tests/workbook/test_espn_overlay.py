"""Build Workbook highlight list from ESPN rosters + matchup rows."""

from draft_api.espn_roster import EspnRosterPlayer
from draft_api.workbook.espn_overlay import build_highlights, highlights_to_json


def _games_ne_nyj() -> list[dict]:
    return [
        {
            "home": "NE",
            "away": "NYJ",
            "rows": [
                {"team": "NE", "opponent": "NYJ"},
                {"team": "NYJ", "opponent": "NE"},
            ],
        }
    ]


def test_roster_wr_on_ne_highlights_ne_row() -> None:
    roster = [
        EspnRosterPlayer(
            player_id=1,
            full_name="Stefon Diggs",
            nfl_team="NE",
            roster_slot="WR",
            lineup_slot="WR",
            injury_status=None,
            espn_team_id=7,
            availability="ONTEAM",
        )
    ]
    highlights, stats = build_highlights(
        games=_games_ne_nyj(),
        roster=roster,
        free_agents=[],
        owner_team_id=None,
    )
    assert len(highlights) == 1
    assert highlights[0].matchup_team == "NE"
    assert highlights[0].opponent == "NYJ"
    assert highlights[0].role == "roster"
    assert stats["matched"] == 1
    assert stats["unmatched_team"] == 0


def test_free_agent_on_board_team() -> None:
    free_agents = [
        EspnRosterPlayer(
            player_id=2,
            full_name="Allen Lazard",
            nfl_team="NYJ",
            roster_slot="WR",
            lineup_slot=None,
            injury_status=None,
            espn_team_id=None,
            availability="FREEAGENT",
        )
    ]
    highlights, stats = build_highlights(
        games=_games_ne_nyj(),
        roster=[],
        free_agents=free_agents,
        owner_team_id=None,
    )
    assert highlights[0].role == "free_agent"
    assert highlights[0].matchup_team == "NYJ"
    assert stats["matched"] == 1


def test_player_on_bye_counts_unmatched_team() -> None:
    roster = [
        EspnRosterPlayer(
            player_id=3,
            full_name="Christian McCaffrey",
            nfl_team="SF",
            roster_slot="RB",
            lineup_slot="RB",
            injury_status=None,
            espn_team_id=11,
            availability="ONTEAM",
        )
    ]
    highlights, stats = build_highlights(
        games=_games_ne_nyj(),
        roster=roster,
        free_agents=[],
        owner_team_id=None,
    )
    assert highlights == []
    assert stats["unmatched_team"] == 1
    assert stats["matched"] == 0


def test_owner_team_id_filters_roster_only() -> None:
    roster = [
        EspnRosterPlayer(
            player_id=1,
            full_name="Stefon Diggs",
            nfl_team="NE",
            roster_slot="WR",
            lineup_slot="WR",
            injury_status=None,
            espn_team_id=7,
            availability="ONTEAM",
        ),
        EspnRosterPlayer(
            player_id=3,
            full_name="Other Owner WR",
            nfl_team="NE",
            roster_slot="WR",
            lineup_slot="WR",
            injury_status=None,
            espn_team_id=99,
            availability="ONTEAM",
        ),
    ]
    highlights, _ = build_highlights(
        games=_games_ne_nyj(),
        roster=roster,
        free_agents=[],
        owner_team_id=7,
    )
    assert len(highlights) == 1
    assert highlights[0].display_name == "Stefon Diggs"


def test_highlights_to_json_camel_case() -> None:
    roster = [
        EspnRosterPlayer(
            player_id=1,
            full_name="Stefon Diggs",
            nfl_team="NE",
            roster_slot="WR",
            lineup_slot="WR",
            injury_status=None,
            espn_team_id=7,
            availability="ONTEAM",
        )
    ]
    highlights, stats = build_highlights(
        games=_games_ne_nyj(),
        roster=roster,
        free_agents=[],
        owner_team_id=None,
    )
    payload = highlights_to_json(highlights, stats)
    assert payload["joinStats"]["matched"] == 1
    row = payload["highlights"][0]
    assert row["playerId"] == 1
    assert row["displayName"] == "Stefon Diggs"
    assert row["matchupTeam"] == "NE"
