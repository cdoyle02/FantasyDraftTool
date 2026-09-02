from cheatsheet import DEFAULT_CHEATSHEET, cheatsheet_metadata
from merge import Projection, RankedPlayer, SeedPlayer, apply_v41_metadata, merge_rankings, player_key


def test_cheatsheet_metadata_includes_upside_for_skill_players() -> None:
    metadata = cheatsheet_metadata(DEFAULT_CHEATSHEET)
    gibbs = metadata[player_key("Jahmyr Gibbs", "RB")]
    assert gibbs.upside_score is not None
    assert gibbs.upside_score > 5
    assert gibbs.risk_score is not None


def test_apply_v41_metadata_preserves_core_ranking_fields() -> None:
    players = merge_rankings(
        [Projection("Jahmyr Gibbs", "DET", "RB", 301.5, consensus_rank=1)],
        {"RB": [RankedPlayer("Jahmyr Gibbs", "DET", "RB", 1, 1)]},
    )
    enriched = apply_v41_metadata(players, cheatsheet_metadata(DEFAULT_CHEATSHEET))
    assert enriched[0].projected_points == players[0].projected_points
    assert enriched[0].adp == players[0].adp
    assert enriched[0].tier == players[0].tier
    assert enriched[0].upside_score is not None
    assert enriched[0].depth_chart_rank == 1
    assert enriched[0].depth_chart_source == "derived"


def test_missing_cheatsheet_metadata_leaves_player_unchanged() -> None:
    player = SeedPlayer(
        "unknown-rb-fa-rb",
        "Unknown Back",
        "RB",
        "FA",
        42.0,
        250.0,
        5,
    )
    enriched = apply_v41_metadata([player], cheatsheet_metadata(DEFAULT_CHEATSHEET))
    assert enriched[0].upside_score is None
    assert enriched[0].depth_chart_rank is None
