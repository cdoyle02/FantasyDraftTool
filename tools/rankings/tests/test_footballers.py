from pathlib import Path

import pytest
from footballers import (
    DEFAULT_WORKBOOK,
    footballers_inputs,
    ppr_season_points,
)
from generate import SEED_VERSION, _load_footballers_hybrid
from merge import MergeConfig, merge_rankings
from store import load_config

HERE = Path(__file__).resolve().parents[1]
CONFIG = HERE / "experts.json"


def test_ppr_season_points_flex_example() -> None:
    # Gibbs comparison-sheet averages (rounded in the workbook).
    points = ppr_season_points(
        rush_yds=1368.33,
        rush_td=13.67,
        rec=74.67,
        rec_yds=639.67,
        rec_td=4.33,
        fum=2.0,
    )
    assert 377 <= points <= 381


def test_footballers_workbook_covers_skill_positions() -> None:
    projections, pooled, consensus = footballers_inputs(DEFAULT_WORKBOOK)
    assert len(projections) == 314
    assert {position: len(rows) for position, rows in pooled.items()} == {
        "QB": 36,
        "RB": 93,
        "WR": 131,
        "TE": 54,
    }
    assert pooled.keys() == consensus.keys()


def test_gibbs_projected_near_workbook_consensus() -> None:
    projections, _, _ = footballers_inputs(DEFAULT_WORKBOOK)
    gibbs = next(item for item in projections if item.name == "Jahmyr Gibbs")
    assert gibbs.position == "RB"
    assert gibbs.fpts == 379.0
    assert gibbs.consensus_rank == 1


def test_qb_uses_counting_stats_not_ppg() -> None:
    projections, _, _ = footballers_inputs(DEFAULT_WORKBOOK)
    allen = next(item for item in projections if item.name == "Josh Allen")
    ppg_season = 21.0 * 17
    assert allen.fpts == 366.6
    assert allen.fpts > ppg_season


def test_positional_ranks_not_flex_ranks() -> None:
    projections, pooled, _ = footballers_inputs(DEFAULT_WORKBOOK)
    chase = next(item for item in projections if item.name == "Ja'Marr Chase")
    assert chase.position == "WR"
    assert chase.consensus_rank <= 5
    wr_ranks = [player.rank for player in pooled["WR"]]
    assert wr_ranks == list(range(1, len(wr_ranks) + 1))


def test_hybrid_seed_includes_k_dst_and_skill_players() -> None:
    config = load_config(CONFIG)
    source, projections, pooled, consensus, adp_rows, _, _, _ = _load_footballers_hybrid(
        config,
        from_data=True,
    )
    players = merge_rankings(
        projections,
        pooled,
        consensus=consensus,
        adp_rows=adp_rows,
        config=MergeConfig(),
    )
    positions = {player.position for player in players}
    assert source == "footballers+cheatsheet+bundled-k-dst"
    assert positions == {"QB", "RB", "WR", "TE", "K", "DST"}
    assert len(players) >= 370
    by_name = {player.name: player for player in players}
    assert by_name["Jahmyr Gibbs"].projected_points == 379.0
    assert by_name["Jahmyr Gibbs"].adp == 1.9
    assert by_name["Jahmyr Gibbs"].tier == 1
    assert by_name["Josh Allen"].adp == 21.0
    assert by_name["Justin Tucker"].position == "K"
    assert by_name["Brandon Aubrey"].adp == 118.2
    assert by_name["Jets DST"].position == "DST"
    unmatched = next(
        player
        for player in players
        if player.position in {"QB", "RB", "WR", "TE"} and player.adp == 250.0
    )
    assert unmatched.tier >= 1


def test_seed_version_bumped() -> None:
    assert SEED_VERSION == "2026.6"


def test_workbook_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        footballers_inputs(Path("missing-workbook.xlsx"))
