from pathlib import Path

import pytest
from cheatsheet import (
    DEFAULT_CHEATSHEET,
    cheatsheet_inputs,
    overlay_cheatsheet_tiers,
)
from merge import RankedPlayer, player_key


def test_cheatsheet_covers_skill_stars() -> None:
    ranked, adp_rows = cheatsheet_inputs(DEFAULT_CHEATSHEET)
    gibbs = ranked[player_key("Jahmyr Gibbs", "RB")]
    allen_adp = next(row for row in adp_rows if row.name == "Josh Allen")
    daniels = ranked[player_key("Jayden Daniels", "QB")]
    burrow = ranked[player_key("Joe Burrow", "QB")]

    assert gibbs.tier == 1
    assert gibbs.rank == 1
    assert next(row.adp for row in adp_rows if row.name == "Jahmyr Gibbs") == 1.9
    assert allen_adp.adp == 21.0
    assert daniels.tier == 4
    assert burrow.tier == 4
    assert {row.position for row in adp_rows} <= {"QB", "RB", "WR", "TE"}
    assert all(row.adp > 0 for row in adp_rows)


def test_overlay_keeps_workbook_ranks_and_unmatched_gap_tiers() -> None:
    cheatsheet = {
        player_key("Jahmyr Gibbs", "RB"): RankedPlayer(
            "Jahmyr Gibbs", "DET", "RB", rank=1, tier=1
        ),
    }
    overlaid = overlay_cheatsheet_tiers(
        {
            "RB": [
                RankedPlayer("Jahmyr Gibbs", "DET", "RB", rank=2, tier=3),
                RankedPlayer("Deep Bench Back", "FA", "RB", rank=40, tier=8),
            ]
        },
        cheatsheet,
    )

    by_name = {row.name: row for row in overlaid["RB"]}
    assert by_name["Jahmyr Gibbs"].tier == 1
    assert by_name["Jahmyr Gibbs"].rank == 2
    assert by_name["Deep Bench Back"].tier == 8
    assert by_name["Deep Bench Back"].rank == 40


def test_cheatsheet_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        cheatsheet_inputs(Path("missing-cheatsheet.csv"))
