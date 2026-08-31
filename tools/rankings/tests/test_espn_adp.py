from espn_adp import (
    espn_adp_from_player,
    espn_adp_rows,
    livedraft_filter,
    livedraft_url,
    read_espn_snapshot,
    write_espn_snapshot,
)
from merge import AdpRow


def test_prefers_ownership_average_draft_position() -> None:
    assert espn_adp_from_player(
        {
            "ownership": {"averageDraftPosition": 2.4},
            "draftRanksByRankType": {"PPR": {"rank": 8}},
        }
    ) == 2.4


def test_falls_back_to_ppr_draft_rank() -> None:
    assert espn_adp_from_player({"draftRanksByRankType": {"PPR": {"rank": 12}}}) == 12.0


def test_skips_players_without_adp() -> None:
    rows = espn_adp_rows(
        [
            {"fullName": "Ja'Marr Chase", "defaultPositionId": 3, "ownership": {"averageDraftPosition": 1.6}},
            {"fullName": "Unknown", "defaultPositionId": 2},
        ]
    )
    assert len(rows) == 1
    assert rows[0].name == "Ja'Marr Chase"
    assert rows[0].position == "WR"
    assert rows[0].adp == 1.6
    assert rows[0].espn_adp == 1.6


def test_livedraft_url_targets_ppr_leaguedefaults() -> None:
    assert livedraft_url(2026) == (
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026"
        "/segments/0/leaguedefaults/3?view=kona_player_info"
    )
    assert livedraft_filter(50)["players"]["sortDraftRanks"]["value"] == "PPR"


def test_snapshot_round_trip(tmp_path) -> None:
    path = tmp_path / "espn-adp.csv"
    write_espn_snapshot(
        [AdpRow("Ja'Marr Chase", "CIN", "WR", 4.3, espn_adp=4.3)],
        path,
    )
    rows = read_espn_snapshot(path)
    assert rows[0].name == "Ja'Marr Chase"
    assert rows[0].adp == 4.3
    assert rows[0].espn_adp == 4.3
