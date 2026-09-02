import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Pick,
    Player,
    Position,
    apply_pick,
    compute_survival_maps,
    recommend,
    team_on_clock,
    tier_cliff,
    tier_opportunity_cost,
    wait_loss_v4,
)
from dvs_engine.formula import expected_startable_slots, picks_until_team_turn
from dvs_engine.lookahead import (
    MarginalCache,
    build_lookahead_pool,
    expected_fallback_value,
    wait_value,
)
from dvs_engine.simulate import simulate_one_turn
from dvs_engine.survival import (
    calibrate_survival_probabilities,
    intervening_opponent_picks,
    intervening_pick_schedule,
)
from dvs_engine.tiers import tier_exhaustion_probability
from dvs_engine.v4 import recommend_v4, shape_adjustment


def _league(**overrides) -> LeagueSettings:
    base = {
        "team_count": 12,
        "roster_slots": {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "SUPERFLEX": 0,
            "BENCH": 6,
            "K": 1,
            "DST": 1,
        },
        "user_team_id": "1",
        "formula_params": FormulaParams(),
    }
    base.update(overrides)
    return LeagueSettings(**base)


def test_wait_loss_identity():
    marginal = 80.0
    fallback = 50.0
    survival = 0.9
    assert wait_loss_v4(marginal, fallback, survival) == pytest.approx(3.0)
    assert wait_loss_v4(marginal, fallback, 0.1) == pytest.approx(27.0)
    assert wait_value(
        Player("x", "X", Position.RB),
        marginal,
        fallback,
        survival,
    ) == pytest.approx(survival * marginal + (1 - survival) * fallback)


def test_high_survival_produces_low_wait_loss():
    marginal = 100.0
    fallback = 60.0
    high = wait_loss_v4(marginal, fallback, 0.9)
    low = wait_loss_v4(marginal, fallback, 0.1)
    assert high < low
    assert high == pytest.approx(4.0)


def test_fallback_strength_affects_wait_loss():
    marginal = 100.0
    survival = 0.5
    weak = wait_loss_v4(marginal, 20.0, survival)
    strong = wait_loss_v4(marginal, 90.0, survival)
    assert weak > strong
    assert strong == pytest.approx(5.0)


def test_expected_fallback_value_uses_survival_chain():
    elite = Player("rb-1", "Elite", Position.RB, projected_points=250, adp=10.0)
    backup = Player("rb-2", "Backup", Position.RB, projected_points=200, adp=100.0)
    marginals = {"rb-1": 100.0, "rb-2": 70.0}
    survival = {"rb-1": 0.2, "rb-2": 0.8}
    fallback = expected_fallback_value(elite, [elite, backup], marginals, survival)
    assert fallback == pytest.approx(70.0 * 0.8)


def test_tier_opportunity_cost_is_capped():
    rb = Player("rb-1", "RB", Position.RB, projected_points=245, adp=20.0, tier=2)
    rb2 = Player("rb-2", "RB2", Position.RB, projected_points=241, adp=21.0, tier=2)
    rb3 = Player("rb-3", "RB3", Position.RB, projected_points=218, adp=40.0, tier=3)
    pool = [rb, rb2, rb3]
    params = FormulaParams()
    survival = {"rb-1": 0.2, "rb-2": 0.3, "rb-3": 0.9}
    cliff = tier_cliff(rb, pool)
    cost = tier_opportunity_cost(rb, pool, survival, params)
    assert cliff == pytest.approx(23.0)
    assert cost <= params.tier_weight * params.tier_cliff_scale


def test_survival_calibration_matches_intervening_picks():
    raw = {"a": 0.4, "b": 0.5, "c": 0.6, "d": 0.7}
    calibrated = calibrate_survival_probabilities(raw, intervening_picks=3, params=FormulaParams())
    drafted = sum(1.0 - calibrated[player_id] for player_id in raw)
    assert drafted == pytest.approx(3.0, abs=0.05)


def test_v4_score_matches_decomposition():
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
        Player("rb-2", "RB2", Position.RB, projected_points=240, adp=30.0, tier=2),
        Player("wr-2", "WR2", Position.WR, projected_points=235, adp=31.0, tier=2),
    ]
    league = _league(team_count=4, roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0})
    results = recommend(pool, DraftState(team_count=4), league, limit=4)
    top = results[0]
    params = league.formula_params
    expected = (
        top.breakdown.immediate_value
        + params.wait_loss_weight_v4 * top.breakdown.wait_loss
        + params.tier_weight * top.breakdown.tier_opportunity_cost
        + params.lookahead_weight * top.breakdown.expected_next_pick_value
        + top.breakdown.shape_adjustment
        + top.breakdown.guardrail_adjustment
        + top.breakdown.optionality_value
    )
    assert top.dvs_score == pytest.approx(expected, abs=0.05)
    assert top.breakdown.decision_score == pytest.approx(expected, abs=0.05)


def test_v4_is_deterministic():
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
    ]
    league = _league(team_count=2, roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0})
    state = DraftState(team_count=2)
    first = recommend_v4(pool, state, league, limit=2)
    second = recommend_v4(pool, state, league, limit=2)
    assert first == second


def test_settings_from_dict_parses_formula_version():
    settings = LeagueSettings(
        team_count=12,
        formula_params=FormulaParams(formula_version=3),
    )
    from dvs_engine import settings_from_dict

    parsed = settings_from_dict({"teamCount": 12, "formulaVersion": 3})
    assert parsed.formula_params.formula_version == 3


def test_shape_adjustment_is_bounded():
    params = FormulaParams()
    league = _league()
    value = shape_adjustment(Position.RB, [], league, 1, params)
    assert -params.need_points_cap <= value <= params.need_points_cap


def test_adjusted_survival_differs_from_adp_prior_when_demand_changes():
    qb = Player("qb-7", "QB7", Position.QB, projected_points=280, adp=55.0, tier=2)
    pool = [qb] + [
        Player(f"fill-{index}", f"Fill {index}", Position.WR, projected_points=100, adp=200.0 + index)
        for index in range(40)
    ]
    league = _league()
    state = DraftState(team_count=12)
    player_map = {player.id: player for player in pool}
    adp_prior, _raw, calibrated, opponent_need, _run, _schedule, intervening_count = (
        compute_survival_maps([qb], state, league, player_map, 1, FormulaParams())
    )
    assert intervening_count == 22
    assert adp_prior["qb-7"] > 0
    assert calibrated["qb-7"] > 0
    assert opponent_need["qb-7"] > 0


def _advance_to_pick(team_count: int, target_pick: int) -> DraftState:
    state = DraftState(team_count=team_count)
    rank = 1
    while state.current_pick < target_pick:
        state = apply_pick(state, f"ghost-{state.current_pick}")
        rank += 1
    return state


def test_back_to_back_picks_have_full_survival():
    league = _league(team_count=12)
    state = _advance_to_pick(12, 24)
    assert team_on_clock(state.current_pick, 12) == "1"
    assert picks_until_team_turn(state, "1") == 1
    assert intervening_opponent_picks(state, "1", 1) == []
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=240, adp=24.0, tier=2),
        Player("wr-1", "WR1", Position.WR, projected_points=230, adp=25.0, tier=2),
    ]
    results = recommend_v4(pool, state, league, limit=2)
    for result in results:
        assert result.breakdown.adjusted_survival_probability == pytest.approx(1.0)
        assert result.breakdown.wait_loss == pytest.approx(0.0)
        assert result.breakdown.tier_exhaustion == pytest.approx(0.0)


def test_impossible_tier_exhaustion_is_zero():
    rb_a = Player("rb-a", "RB A", Position.RB, projected_points=240, adp=2.0, tier=2)
    rb_b = Player("rb-b", "RB B", Position.RB, projected_points=239, adp=3.0, tier=2)
    assert tier_exhaustion_probability(rb_a, [rb_a, rb_b], {}, intervening_picks=1) == 0.0
    league = _league(
        team_count=2,
        roster_slots={"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
    )
    state = DraftState(team_count=2, pick_history=(Pick(1, "2", "ghost-1"), Pick(2, "1", "ghost-2")))
    schedule = intervening_pick_schedule(state, "1", picks_until_team_turn(state, "1"))
    assert len(schedule) == 1
    results = recommend_v4([rb_a, rb_b], state, league, limit=2)
    for result in results:
        assert result.breakdown.tier_exhaustion == pytest.approx(0.0)


def test_opponent_two_picks_updates_need():
    rb1 = Player("rb-1", "RB1", Position.RB, projected_points=250, adp=1.0, tier=1)
    rb2 = Player("rb-2", "RB2", Position.RB, projected_points=240, adp=2.0, tier=1)
    wr1 = Player("wr-1", "WR1", Position.WR, projected_points=230, adp=3.0, tier=1)
    fillers = [
        Player(f"fill-{index}", f"Fill {index}", Position.WR, projected_points=100, adp=50.0 + index)
        for index in range(20)
    ]
    pool = [rb1, rb2, wr1, *fillers]
    params = FormulaParams(one_turn_sims=400, sim_seed=42)
    league = LeagueSettings(
        team_count=2,
        roster_slots={"QB": 0, "RB": 2, "WR": 2, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
        user_team_id="1",
        formula_params=params,
    )
    state = DraftState(team_count=2)
    player_map = {player.id: player for player in pool}
    schedule = intervening_pick_schedule(state, "1", picks_until_team_turn(state, "1"))
    assert len(schedule) == 2
    assert schedule[0][1] == schedule[1][1] == "2"
    from dvs_engine.survival import run_pressure_by_position

    run_pressure = run_pressure_by_position(state, player_map, league, params)
    marginals = {player.id: player.projected_points for player in pool}
    lookahead_pool = build_lookahead_pool(pool, marginals, params)
    sim_result = simulate_one_turn(
        pool,
        marginals,
        lookahead_pool,
        schedule,
        state,
        league,
        player_map,
        1,
        run_pressure,
        params,
    )
    assert sim_result.survival_by_id["rb-1"] < sim_result.survival_by_id["rb-2"]

    second_pick_rbs = 0
    second_pick_total = 0
    rng = __import__("random").Random(params.sim_seed)
    base_rosters = {team_id: list(players) for team_id, players in state.rosters.items()}
    from dvs_engine.simulate import _sample_pick

    for _ in range(400):
        remaining = {player.id for player in pool}
        simulated_rosters = {team_id: list(players) for team_id, players in base_rosters.items()}
        picks: list[Player | None] = []
        for pick_number, team_id in schedule:
            remaining_players = [player_map[player_id] for player_id in remaining]
            picked = _sample_pick(
                rng,
                remaining_players,
                pick_number,
                team_id,
                simulated_rosters,
                player_map,
                league,
                1,
                run_pressure,
                params,
                params.sim_pick_pool,
            )
            picks.append(picked)
            if picked is None:
                continue
            remaining.remove(picked.id)
            simulated_rosters.setdefault(team_id, []).append(picked.id)
        if len(picks) == 2 and picks[0] is not None and picks[1] is not None:
            second_pick_total += 1
            if picks[0].position == Position.RB and picks[1].position == Position.RB:
                second_pick_rbs += 1
    assert second_pick_total > 0
    assert second_pick_rbs / second_pick_total < 0.5


def test_flex_run_baseline_uses_weighted_allocation():
    league = _league()
    startable = expected_startable_slots(league)
    assert startable[Position.RB] == pytest.approx(2.45)
    assert startable[Position.WR] == pytest.approx(2.45)
    assert startable[Position.TE] == pytest.approx(1.10)
    assert sum(startable.values()) == pytest.approx(9.0)


def test_shallow_vs_deep_position_lookahead():
    """Filling the lone TE slot first leaves higher WR opportunity at the next pick."""
    te_only = Player("te-1", "TE1", Position.TE, projected_points=220, adp=5.0, tier=1)
    wr_top = Player("wr-top", "WR Top", Position.WR, projected_points=220, adp=6.0, tier=1)
    wrs = [
        Player(f"wr-{index}", f"WR {index}", Position.WR, projected_points=210 - index, adp=10.0 + index)
        for index in range(8)
    ]
    league = _league(
        team_count=2,
        roster_slots={"QB": 0, "RB": 0, "WR": 2, "TE": 1, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
    )
    pool = [te_only, wr_top, *wrs]
    state = DraftState(
        team_count=2,
        pick_history=(
            Pick(1, "1", "ghost-1"),
            Pick(2, "2", "ghost-2"),
            Pick(3, "2", "ghost-3"),
        ),
    )
    assert intervening_opponent_picks(state, "1", picks_until_team_turn(state, "1")) == []
    results = {item.player_id: item for item in recommend_v4(pool, state, league, limit=len(pool))}
    te_next_after_te = results["te-1"].breakdown.expected_next_pick_value
    wr_next_after_wr = results["wr-top"].breakdown.expected_next_pick_value
    assert te_next_after_te > wr_next_after_wr
    assert te_next_after_te > 0.0
    assert wr_next_after_wr > 0.0


def _scenario_pool_for_test(*featured: Player) -> list[Player]:
    fillers = [
        Player(
            f"fill-{index}",
            f"Filler {index}",
            position=Position.RB if index % 2 == 0 else Position.WR,
            projected_points=45.0,
            adp=400.0 + index,
            tier=5,
        )
        for index in range(80)
    ]
    return [*featured, *fillers]


def test_simulated_probabilities_are_bounded():
    pool = _scenario_pool_for_test(
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
    )
    league = _league()
    results = recommend_v4(pool, DraftState(team_count=12), league, limit=5)
    for result in results:
        survival = result.breakdown.adjusted_survival_probability
        assert 0.0 <= survival <= 1.0
        assert result.breakdown.expected_fallback_value <= result.breakdown.marginal_value + 50
        assert result.breakdown.tier_exhaustion <= 1.0
    rb = next(item for item in results if item.player_id == "rb-1")
    tier_members = 1
    schedule_len = 22
    if tier_members > schedule_len:
        assert rb.breakdown.tier_exhaustion == 0.0


def test_reserved_rosters_remove_players_without_advancing_pick_number():
    pool = _scenario_pool_for_test(
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
    )
    league = _league(user_team_id="6")
    state = DraftState(
        team_count=12,
        reserved_rosters={"6": ("rb-1",)},
    )
    assert state.current_pick == 1
    assert state.rosters["6"] == ("rb-1",)
    assert "rb-1" in state.drafted_ids
    results = recommend_v4(pool, state, league, limit=5)
    assert all(result.player_id != "rb-1" for result in results)
