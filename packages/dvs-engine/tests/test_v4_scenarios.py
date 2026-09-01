import time

import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    apply_pick,
    recommend,
    team_on_clock,
)


TWELVE_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "SUPERFLEX": 0,
    "BENCH": 6,
    "K": 1,
    "DST": 1,
}


def _v4_league(**overrides) -> LeagueSettings:
    base = {
        "team_count": 12,
        "roster_slots": TWELVE_SLOTS,
        "user_team_id": "1",
        "formula_params": FormulaParams(),
    }
    base.update(overrides)
    return LeagueSettings(**base)


def _fillers(count: int) -> list[Player]:
    return [
        Player(
            id=f"fill-{index}",
            name=f"Filler {index}",
            position=Position.WR if index % 2 == 0 else Position.RB,
            projected_points=45.0,
            adp=400.0 + index,
            tier=5,
        )
        for index in range(count)
    ]


def _advance_user_picks(
    pool: list[Player],
    user_ids: tuple[str, ...],
    team_count: int = 12,
    user_team_id: str = "1",
) -> DraftState:
    filler_ids = [player.id for player in pool if player.id.startswith("fill-")]
    filler_index = 0
    used: set[str] = set()
    state = DraftState(team_count)
    user_index = 0
    while user_index < len(user_ids):
        if team_on_clock(state.current_pick, team_count) == user_team_id:
            state = apply_pick(state, user_ids[user_index])
            used.add(user_ids[user_index])
            user_index += 1
        else:
            while filler_ids[filler_index] in used:
                filler_index += 1
            state = apply_pick(state, filler_ids[filler_index])
            used.add(filler_ids[filler_index])
            filler_index += 1
    while team_on_clock(state.current_pick, team_count) != user_team_id:
        while filler_ids[filler_index] in used:
            filler_index += 1
        state = apply_pick(state, filler_ids[filler_index])
        used.add(filler_ids[filler_index])
        filler_index += 1
    return state


def _scenario_pool(*featured: Player) -> list[Player]:
    return [*featured, *_fillers(220)]


def test_scenario_a_last_player_in_elite_tier():
    from dvs_engine.tiers import players_remaining_in_tier, tier_opportunity_cost

    rb_last = Player("rb-last", "RB Last", Position.RB, projected_points=245, adp=24.0, tier=2)
    rb_peer = Player("rb-peer", "RB Peer", Position.RB, projected_points=241, adp=25.0, tier=2)
    rb_next = Player("rb-next", "RB Next", Position.RB, projected_points=218, adp=40.0, tier=3)
    wr = Player("wr-1", "WR1", Position.WR, projected_points=240, adp=26.0, tier=2)
    available = [rb_last, rb_next, wr]
    survival = {player.id: 0.2 for player in available}
    assert players_remaining_in_tier(rb_last, available) == 1
    assert tier_opportunity_cost(rb_last, available, survival, FormulaParams()) > 0
    with_peer = [rb_last, rb_peer, rb_next, wr]
    survival_with_peer = {player.id: 0.2 for player in with_peer}
    alone = tier_opportunity_cost(rb_last, available, survival, FormulaParams())
    crowded = tier_opportunity_cost(rb_last, with_peer, survival_with_peer, FormulaParams())
    assert alone >= crowded


def test_scenario_b_high_survival_player_has_low_wait_loss():
    wr_safe = Player("wr-safe", "WR Safe", Position.WR, projected_points=260, adp=200.0, tier=1)
    rb_scarce = Player("rb-scarce", "RB Scarce", Position.RB, projected_points=255, adp=24.0, tier=1)
    rb_back = Player("rb-back", "RB Back", Position.RB, projected_points=200, adp=210.0, tier=2)
    wr_back = Player("wr-back", "WR Back", Position.WR, projected_points=195, adp=211.0, tier=2)
    pool = _scenario_pool(wr_safe, rb_scarce, rb_back, wr_back)
    settings = _v4_league(team_count=12, roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0})
    results = recommend(pool, DraftState(team_count=12), settings, limit=4)
    safe = next(item for item in results if item.player_id == "wr-safe")
    scarce = next(item for item in results if item.player_id == "rb-scarce")
    assert safe.breakdown.adjusted_survival_probability > scarce.breakdown.adjusted_survival_probability
    if safe.breakdown.marginal_value > 0 and scarce.breakdown.marginal_value > 0:
        assert safe.breakdown.wait_loss <= scarce.breakdown.wait_loss


def test_scenario_c_low_survival_increases_urgency():
    rb_urgent = Player("rb-urgent", "RB Urgent", Position.RB, projected_points=250, adp=24.0, tier=1)
    rb_safe = Player("rb-safe", "RB Safe", Position.RB, projected_points=250, adp=200.0, tier=1)
    pool = _scenario_pool(rb_urgent, rb_safe)
    settings = _v4_league(team_count=12, roster_slots={"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0})
    results = recommend(pool, DraftState(team_count=12), settings, limit=2)
    urgent = next(item for item in results if item.player_id == "rb-urgent")
    safe = next(item for item in results if item.player_id == "rb-safe")
    assert urgent.breakdown.adjusted_survival_probability < safe.breakdown.adjusted_survival_probability
    assert urgent.breakdown.wait_loss >= safe.breakdown.wait_loss


def test_scenario_d_deep_wr_vs_cliff_rb():
    wr = Player("wr-a", "WR A", Position.WR, projected_points=255, adp=24.0, tier=1)
    rb = Player("rb-a", "RB A", Position.RB, projected_points=250, adp=25.0, tier=2)
    wr2 = Player("wr-b", "WR B", Position.WR, projected_points=248, adp=26.0, tier=1)
    wr3 = Player("wr-c", "WR C", Position.WR, projected_points=246, adp=27.0, tier=1)
    rb2 = Player("rb-b", "RB B", Position.RB, projected_points=220, adp=50.0, tier=3)
    pool = [wr, rb, wr2, wr3, rb2]
    settings = _v4_league(team_count=4, roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0})
    results = recommend(pool, DraftState(team_count=4), settings, limit=5)
    rb_result = next(item for item in results if item.player_id == "rb-a")
    wr_result = next(item for item in results if item.player_id == "wr-a")
    assert rb_result.breakdown.tier_cliff > wr_result.breakdown.tier_cliff
    assert results[0].player_id in {"rb-a", "wr-a"}


def test_scenario_e_elite_value_override():
    settings = _v4_league()
    rbs = [
        Player(f"rb-{index}", f"RB{index}", Position.RB, projected_points=220 - index, adp=float(index + 1), tier=2)
        for index in range(6)
    ]
    wrs = [
        Player(f"wr-{index}", f"WR{index}", Position.WR, projected_points=215 - index, adp=float(index + 10), tier=2)
        for index in range(3)
    ]
    elite = Player("wr-elite", "Elite WR", Position.WR, projected_points=420, adp=3.0, tier=1)
    pool = _scenario_pool(*rbs, *wrs, elite)
    user_ids = tuple(player.id for player in (*rbs[:2], *wrs[:2]))
    state = _advance_user_picks(pool, user_ids)
    results = recommend(pool, state, settings, limit=5)
    top = results[0]
    assert top.player_id == "wr-elite"
    assert top.breakdown.immediate_value > 50


def test_scenario_f_late_starter_hole_matters():
    from dvs_engine.v4 import shape_adjustment

    settings = _v4_league()
    wr1 = Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1)
    wr2 = Player("wr-2", "WR2", Position.WR, projected_points=260, adp=3.0, tier=1)
    te1 = Player("te-1", "TE1", Position.TE, projected_points=200, adp=4.0, tier=1)
    early_shape = shape_adjustment(Position.RB, [], settings, 1, settings.formula_params)
    late_shape = shape_adjustment(Position.RB, [wr1, wr2, te1], settings, 13, settings.formula_params)
    assert late_shape > early_shape


def test_scenario_g_opponent_qb_demand_lowers_survival():
    qb = Player("qb-7", "QB7", Position.QB, projected_points=280, adp=55.0, tier=2)
    pool = _scenario_pool(qb)
    settings = _v4_league()
    state = DraftState(team_count=12)
    results = recommend(pool, state, settings, limit=1)
    top = results[0]
    assert top.breakdown.adjusted_survival_probability <= top.breakdown.survival_probability + 0.05


def test_scenario_h_filled_qb_rosters_raise_survival():
    qb = Player("qb-7", "QB7", Position.QB, projected_points=280, adp=55.0, tier=2)
    qbs = [
        Player(f"qb-fill-{index}", f"QB Fill {index}", Position.QB, projected_points=240 - index, adp=10.0 + index, tier=3)
        for index in range(12)
    ]
    pool = _scenario_pool(qb, *qbs)
    settings = _v4_league()
    state = DraftState(team_count=12)
    for pick_number in range(1, 13):
        team = team_on_clock(pick_number, 12)
        state = apply_pick(state, f"qb-fill-{pick_number - 1}" if team != "1" else "fill-0")
    results = recommend(pool, state, settings, limit=1)
    top = results[0]
    assert top.breakdown.survival_probability > 0.5


def test_scenario_i_flex_compares_positions():
    rb = Player("rb-flex", "RB Flex", Position.RB, projected_points=240, adp=20.0, tier=2)
    te = Player("te-flex", "TE Flex", Position.TE, projected_points=230, adp=21.0, tier=2)
    pool = _scenario_pool(rb, te)
    settings = _v4_league()
    results = recommend(pool, DraftState(team_count=12), settings, limit=2)
    assert len(results) == 2
    assert results[0].breakdown.marginal_value >= 0


def test_scenario_j_superflex_values_qb():
    from dvs_engine import marginal_value

    qb = Player("qb-sf", "QB SF", Position.QB, projected_points=320, adp=20.0, tier=1)
    qb_starter = Player("qb-start", "QB Start", Position.QB, projected_points=300, adp=1.0, tier=1)
    levels = {
        Position.QB: 240.0,
        Position.RB: 150.0,
        Position.WR: 150.0,
        Position.TE: 120.0,
    }
    sf_settings = _v4_league(roster_slots={**TWELVE_SLOTS, "SUPERFLEX": 1})
    std_settings = _v4_league()
    params = FormulaParams()
    roster = [qb_starter]
    sf_qb = marginal_value(qb, roster, sf_settings, levels, params)
    std_qb = marginal_value(qb, roster, std_settings, levels, params)
    assert sf_qb > std_qb


def test_scenario_k_same_tier_players_stay_close():
    rb_a = Player("rb-a", "RB A", Position.RB, projected_points=240, adp=24.0, tier=2)
    rb_b = Player("rb-b", "RB B", Position.RB, projected_points=239, adp=25.0, tier=2)
    rb_c = Player("rb-c", "RB C", Position.RB, projected_points=220, adp=40.0, tier=3)
    pool = _scenario_pool(rb_a, rb_b, rb_c)
    settings = _v4_league(team_count=2, roster_slots={"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0})
    results = recommend(pool, DraftState(team_count=2), settings, limit=2)
    a = next(item for item in results if item.player_id == "rb-a")
    b = next(item for item in results if item.player_id == "rb-b")
    assert abs(a.breakdown.tier_opportunity_cost - b.breakdown.tier_opportunity_cost) < 2.0


def test_scenario_l_need_influence_grows_over_draft():
    from dvs_engine.v4 import shape_adjustment

    settings = _v4_league()
    wr1 = Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1)
    wr2 = Player("wr-2", "WR2", Position.WR, projected_points=260, adp=3.0, tier=1)
    te1 = Player("te-1", "TE1", Position.TE, projected_points=200, adp=4.0, tier=1)
    early = shape_adjustment(Position.RB, [], settings, 1, settings.formula_params)
    late = shape_adjustment(Position.RB, [wr1, wr2, te1], settings, 13, settings.formula_params)
    assert late > early


def test_v4_performance_budget():
    specs = {
        Position.QB: [320 - index * 5 for index in range(20)],
        Position.RB: [290 - index * 3 for index in range(60)],
        Position.WR: [285 - index * 3 for index in range(60)],
        Position.TE: [230 - index * 4 for index in range(30)],
        Position.K: [130 - index for index in range(20)],
        Position.DST: [125 - index for index in range(20)],
    }
    pool: list[Player] = []
    rank = 1
    for position, projections in specs.items():
        for index, points in enumerate(projections, start=1):
            pool.append(
                Player(
                    id=f"{position.value.lower()}-{index}",
                    name=f"{position.value} {index}",
                    position=position,
                    projected_points=points,
                    adp=float(rank),
                    tier=1 if index <= 3 else 2 if index <= 8 else 3,
                )
            )
            rank += 1
    settings = _v4_league()
    state = DraftState(team_count=12)
    started = time.perf_counter()
    results = recommend(pool, state, settings, limit=20)
    elapsed = time.perf_counter() - started
    assert len(results) == 20
    assert elapsed < 2.0
