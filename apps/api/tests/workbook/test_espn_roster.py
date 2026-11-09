"""ESPN roster + FA fetch for Workbook overlay (fixture HTTP only)."""

import json
from pathlib import Path

import pytest

from draft_api.espn_roster import (
    EspnRosterError,
    EspnRosterPlayer,
    fetch_league_free_agents,
    fetch_league_roster,
    parse_league_roster,
    resolve_owner_team_id,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROSTER_MINI = FIXTURES / "espn_roster_mini.json"

FA_MINI = {
    "players": [
        {
            "status": "FREEAGENT",
            "player": {
                "id": 3045147,
                "fullName": "Allen Lazard",
                "defaultPositionId": 3,
                "proTeamId": 20,
                "injuryStatus": "",
            },
        },
        {
            "status": "WAIVERS",
            "player": {
                "id": 16737,
                "fullName": "Mike Gesicki",
                "defaultPositionId": 4,
                "proTeamId": 4,
                "injuryStatus": "",
            },
        },
    ]
}


def _load_roster_fixture() -> dict:
    return json.loads(ROSTER_MINI.read_text(encoding="utf-8"))


def test_parse_league_roster_returns_team_id_and_slots() -> None:
    players = parse_league_roster(_load_roster_fixture())
    assert len(players) == 2
    diggs = next(p for p in players if p.player_id == 4362628)
    assert diggs.espn_team_id == 7
    assert diggs.nfl_team == "NE"
    assert diggs.full_name == "Stefon Diggs"
    assert diggs.roster_slot == "WR"
    assert diggs.lineup_slot == "WR"
    assert diggs.injury_status is None
    assert diggs.availability == "ONTEAM"


def test_resolve_owner_team_id_by_display_name() -> None:
    payload = _load_roster_fixture()
    assert resolve_owner_team_id(payload, owner="Katie") == 11
    assert resolve_owner_team_id(payload, owner="michael") == 7


def test_fetch_league_roster_uses_http_json_override() -> None:
    fixture = _load_roster_fixture()

    def fake_http(url: str, headers: dict[str, str]) -> dict:
        assert "1216398267" in url
        assert "mRoster" in url or "view=" in url
        assert headers["Cookie"]
        return fixture

    players = fetch_league_roster(
        league_id="1216398267",
        season=2026,
        espn_s2="s2",
        swid="{SWID}",
        http_json=fake_http,
    )
    assert len(players) == 2
    assert isinstance(players[0], EspnRosterPlayer)


def test_fetch_league_free_agents_uses_http_json_override() -> None:
    def fake_http(url: str, headers: dict[str, str]) -> dict:
        assert "kona_player_info" in url or "view" in url
        return FA_MINI

    players = fetch_league_free_agents(
        league_id="1216398267",
        season=2026,
        espn_s2="s2",
        swid="{SWID}",
        http_json=fake_http,
    )
    assert len(players) == 2
    roles = {p.full_name: p.availability for p in players}
    assert roles["Allen Lazard"] == "FREEAGENT"
    assert roles["Mike Gesicki"] == "WAIVERS"
    assert all(p.espn_team_id is None for p in players)


def test_fetch_league_roster_invalid_payload_raises() -> None:
    def fake_http(url: str, headers: dict[str, str]) -> dict:
        return {"not_teams": []}

    with pytest.raises(EspnRosterError, match="unexpected"):
        fetch_league_roster(
            league_id="1",
            season=2026,
            espn_s2="s2",
            swid="{SWID}",
            http_json=fake_http,
        )
