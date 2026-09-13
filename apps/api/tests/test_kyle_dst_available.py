from draft_api.espn_leagues import get_league, leagues_payload, load_espn_leagues
from draft_api.kyle_dst_available import build_kyle_available_payload, cross_ref_available, teams_match


def test_load_espn_leagues_includes_known_leagues():
    load_espn_leagues.cache_clear()
    leagues = load_espn_leagues()
    by_id = {league["id"]: league["name"] for league in leagues}
    assert by_id["1216398267"] == "Girls Who Ball"
    assert by_id["169429"] == "Florida Football Federation"
    assert by_id["853476190"] == "Two Flex Too Furious"
    assert by_id["886805"] == "Just The Tip"
    assert leagues_payload()["leagues"] == leagues


def test_get_league():
    load_espn_leagues.cache_clear()
    league = get_league("1216398267")
    assert league["name"] == "Girls Who Ball"
    assert get_league("886805")["name"] == "Just The Tip"


def test_teams_match_aliases():
    assert teams_match("JAX", "JAC")
    assert teams_match("WAS", "WSH")
    assert not teams_match("KC", "BUF")


def test_cross_ref_available_preserves_kyle_order():
    rankings = [
        {"rank": 1, "team": "JAX", "teamName": "Jacksonville Jaguars", "opponent": "vs. CLE", "ecr": 1, "vsEcr": "0"},
        {"rank": 2, "team": "LAC", "teamName": "Los Angeles Chargers", "opponent": "vs. ARI", "ecr": 2, "vsEcr": "0"},
        {"rank": 3, "team": "TEN", "teamName": "Tennessee Titans", "opponent": "vs. NYJ", "ecr": 10, "vsEcr": "+7"},
    ]
    available = [
        {"team": "JAC", "status": "FREEAGENT", "percentOwned": 12.5, "name": "Jaguars D/ST"},
        {"team": "TEN", "status": "WAIVERS", "percentOwned": 4.0, "name": "Titans D/ST"},
    ]
    rows = cross_ref_available(rankings, available)
    assert [row["team"] for row in rows] == ["JAX", "TEN"]
    assert rows[0]["status"] == "FREEAGENT"
    assert rows[1]["percentOwned"] == 4.0


def test_cross_ref_available_alias_overwrite_keeps_bidirectional_consistent():
    """Both abbrevs must track the last-wins row (setdefault left WAS stale)."""
    rankings = [
        {
            "rank": 1,
            "team": "WAS",
            "teamName": "Washington Commanders",
            "opponent": "vs. PHI",
            "ecr": 8,
            "vsEcr": "-2",
        },
    ]
    available = [
        {"team": "WAS", "status": "FREEAGENT", "percentOwned": 1.0, "name": "Commanders D/ST"},
        {"team": "WSH", "status": "WAIVERS", "percentOwned": 99.0, "name": "Commanders D/ST"},
    ]
    rows = cross_ref_available(rankings, available)
    assert len(rows) == 1
    assert rows[0]["status"] == "WAIVERS"
    assert rows[0]["percentOwned"] == 99.0


def test_build_kyle_available_payload():
    payload = build_kyle_available_payload(
        rankings_payload={
            "week": 1,
            "fetchedAt": "2026-09-13T12:00:00Z",
            "sourceUrl": "https://example.test",
            "rankings": [
                {"rank": 1, "team": "KC", "teamName": "Kansas City Chiefs", "opponent": "vs. LV", "ecr": 5, "vsEcr": "-1"},
            ],
        },
        available=[{"team": "KC", "status": "FREEAGENT", "percentOwned": 40.0}],
        league={"id": "1", "name": "Test"},
    )
    assert payload["leagueId"] == "1"
    assert payload["available"][0]["team"] == "KC"
