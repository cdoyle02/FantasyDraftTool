from merge import (
    AdpRow,
    MergeConfig,
    Projection,
    RankedPlayer,
    gap_tiers,
    merge_rankings,
    normalize_name,
    normalize_position,
)


def test_specialist_nudge_adds_a_few_points_not_a_new_wr1() -> None:
    players = merge_rankings(
        [Projection("George Pickens", "DAL", "WR", 246.2, consensus_rank=7)],
        {"WR": [RankedPlayer("George Pickens", "DAL", "WR", 1, 1)]},
        consensus={"WR": [RankedPlayer("George Pickens", "DAL", "WR", 7, 2)]},
        adp_rows=[AdpRow("George Pickens", "DAL", "WR", 38.4)],
        config=MergeConfig(k=0.6, nudge_clamp=8.0),
    )

    assert players[0].projected_points == 249.8
    assert players[0].tier == 1
    assert players[0].adp == 38.4


def test_nudge_is_clamped_so_totals_stay_realistic() -> None:
    players = merge_rankings(
        [Projection("Boom Player", "KC", "WR", 200.0, consensus_rank=40)],
        {"WR": [RankedPlayer("Boom Player", "KC", "WR", 1)]},
        consensus={"WR": [RankedPlayer("Boom Player", "KC", "WR", 40)]},
        config=MergeConfig(k=2.0, nudge_clamp=8.0),
    )

    assert players[0].projected_points == 208.0


def test_name_normalization_drops_generational_suffixes() -> None:
    assert normalize_name("James Cook III") == normalize_name("James Cook")
    assert normalize_name("Aaron Jones Sr.") == normalize_name("Aaron Jones")


def test_dst_aliases_normalize_to_dst() -> None:
    assert normalize_position("D/ST") == "DST"
    players = merge_rankings(
        [Projection("Jets Defense", "NYJ", "D/ST", 128.0)],
        {"DST": [RankedPlayer("Jets Defense", "NYJ", "D/ST", 2, 2)]},
        adp_rows=[AdpRow("Jets Defense", "NYJ", "DEF", 132.0)],
    )

    assert players[0].position == "DST"
    assert players[0].id == "jets-defense-nyj-dst"


def test_missing_adp_uses_configured_default() -> None:
    players = merge_rankings(
        [Projection("Justin Tucker", "BAL", "K", 151.0)],
        {"K": [RankedPlayer("Justin Tucker", "BAL", "K", 1)]},
        config=MergeConfig(missing_adp=250.0),
    )

    assert players[0].adp == 250.0


def test_projection_only_players_stay_in_the_pool() -> None:
    players = merge_rankings(
        [
            Projection("Bijan Robinson", "ATL", "RB", 301.5, consensus_rank=1),
            Projection("Deep Bench Back", "FA", "RB", 42.0),
        ],
        {"RB": [RankedPlayer("Bijan Robinson", "ATL", "RB", 1, 1)]},
        adp_rows=[AdpRow("Bijan Robinson", "ATL", "RB", 4.2)],
        config=MergeConfig(missing_adp=250.0),
    )

    by_name = {player.name: player for player in players}
    assert by_name["Deep Bench Back"].projected_points == 42.0
    assert by_name["Deep Bench Back"].adp == 250.0
    assert by_name["Deep Bench Back"].tier >= 1


def test_gap_tiers_open_a_new_tier_on_large_rank_jumps() -> None:
    assert gap_tiers([1, 2, 6, 7], threshold=4) == [1, 1, 2, 2]


def test_platform_adps_attach_and_dedicated_rows_override() -> None:
    players = merge_rankings(
        [Projection("Bijan Robinson", "ATL", "RB", 301.5, consensus_rank=1)],
        {"RB": [RankedPlayer("Bijan Robinson", "ATL", "RB", 1, 1)]},
        adp_rows=[AdpRow("Bijan Robinson", "ATL", "RB", 4.2, espn_adp=3.8, sleeper_adp=4.5)],
        espn_adp_rows=[AdpRow("Bijan Robinson", "ATL", "RB", 3.1)],
        sleeper_adp_rows=[],
    )

    assert players[0].adp == 4.2
    assert players[0].espn_adp == 3.1
    assert players[0].sleeper_adp == 4.5


def test_missing_platform_adps_stay_none() -> None:
    players = merge_rankings(
        [Projection("Justin Tucker", "BAL", "K", 151.0)],
        {"K": [RankedPlayer("Justin Tucker", "BAL", "K", 1)]},
        config=MergeConfig(missing_adp=250.0),
    )

    assert players[0].adp == 250.0
    assert players[0].espn_adp is None
    assert players[0].sleeper_adp is None
