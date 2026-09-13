from draft_api.jared_k_available import (
    build_jared_available_payload,
    cross_ref_available,
    normalize_player_name,
    teams_match,
)


def test_normalize_player_name():
    assert normalize_player_name("Ka'imi Fairbairn") == "kaimi fairbairn"
    assert normalize_player_name("Chris Godwin Jr.") == "chris godwin"


def test_teams_match_aliases():
    assert teams_match("JAX", "JAC")
    assert teams_match("WAS", "WSH")
    assert not teams_match("KC", "BUF")


def test_cross_ref_available_by_name_preserves_jared_order():
    rankings = [
        {"rank": 1, "player": "Brandon Aubrey", "team": "DAL", "opponent": "at NYG", "ecr": 1, "vsEcr": "0"},
        {"rank": 8, "player": "Evan McPherson", "team": "CIN", "opponent": "vs. TB", "ecr": 5, "vsEcr": "-3"},
        {"rank": 14, "player": "Jake Elliott", "team": "PHI", "opponent": "vs. WAS", "ecr": 15, "vsEcr": "+1"},
    ]
    available = [
        {"name": "Jake Elliott", "team": "PHI", "status": "FREEAGENT", "percentOwned": 8.7},
        {"name": "Evan McPherson", "team": "CIN", "status": "FREEAGENT", "percentOwned": 21.6},
    ]
    rows = cross_ref_available(rankings, available)
    assert [row["player"] for row in rows] == ["Evan McPherson", "Jake Elliott"]
    assert rows[0]["status"] == "FREEAGENT"
    assert rows[0]["percentOwned"] == 21.6


def test_cross_ref_fallback_single_team_match():
    rankings = [
        {"rank": 3, "player": "Cam Little", "team": "JAC", "opponent": "vs. CLE", "ecr": 3, "vsEcr": "0"},
    ]
    available = [
        {"name": "Cameron Little", "team": "JAX", "status": "WAIVERS", "percentOwned": 2.0},
    ]
    rows = cross_ref_available(rankings, available)
    assert len(rows) == 1
    assert rows[0]["team"] == "JAC"
    assert rows[0]["status"] == "WAIVERS"


def test_build_jared_available_payload():
    payload = build_jared_available_payload(
        rankings_payload={
            "week": 1,
            "fetchedAt": "2026-09-13T12:00:00Z",
            "sourceUrl": "https://example.test",
            "rankings": [
                {"rank": 8, "player": "Evan McPherson", "team": "CIN", "opponent": "vs. TB", "ecr": 5, "vsEcr": "-3"},
            ],
        },
        available=[{"name": "Evan McPherson", "team": "CIN", "status": "FREEAGENT", "percentOwned": 21.6}],
        league={"id": "1", "name": "Test"},
    )
    assert payload["leagueId"] == "1"
    assert payload["available"][0]["player"] == "Evan McPherson"
