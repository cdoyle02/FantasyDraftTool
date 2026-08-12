import pytest

from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    RecommendationLabel,
    UserAdjustment,
    apply_pick,
    guardrail_adjustment,
    recommend,
    replacement_counts,
    replacement_levels,
    roster_need_multiplier,
    survival_probability,
    tier_cliff_urgency,
    vorp,
)
from dvs_engine.formula import effective_player, opponent_demand_factor, picks_until_team_turn


def test_replacement_levels_use_first_non_starter(players, settings):
    counts = replacement_counts(settings)
    levels = replacement_levels(players, settings)

    assert counts[Position.QB] == 4
    assert counts[Position.RB] == 6
    assert levels[Position.QB] == 240
    assert levels[Position.RB] == 200
    assert vorp(players[0], levels) == 80


def test_flex_allocation_conserves_total_slots():
    settings = LeagueSettings(team_count=12)
    counts = replacement_counts(settings)
    flex_total = settings.team_count * int(settings.roster_slots["FLEX"])
    flex_allocated = (
        counts[Position.RB]
        - settings.team_count * int(settings.roster_slots["RB"])
        + counts[Position.WR]
        - settings.team_count * int(settings.roster_slots["WR"])
        + counts[Position.TE]
        - settings.team_count * int(settings.roster_slots["TE"])
    )
    assert flex_allocated == flex_total


def test_default_league_replacement_ranks_match_spec_intent():
    settings = LeagueSettings()
    counts = replacement_counts(settings)
    assert counts[Position.QB] == 12
    assert counts[Position.RB] == 30
    assert counts[Position.WR] == 29
    assert counts[Position.TE] == 13


def test_tier_cliff_combines_drop_and_survival(players):
    rb_one = next(player for player in players if player.id == "rb-1")
    urgent = tier_cliff_urgency(rb_one, players, 0.1)
    safe = tier_cliff_urgency(rb_one, players, 0.9)

    assert urgent > safe > 0


def test_survival_probability_declines_as_next_pick_gets_later(players):
    player = players[5]
    soon = survival_probability(player, current_pick=1, picks_until_next=2)
    later = survival_probability(player, current_pick=1, picks_until_next=20)

    assert 0 < later < soon < 1


def test_survival_probability_is_conditional_on_current_availability():
    player = Player(
        id="fallen-rb",
        name="Fallen RB",
        position=Position.RB,
        projected_points=200,
        adp=10.0,
        tier=1,
    )
    conditional = survival_probability(player, current_pick=50, picks_until_next=10)
    early = survival_probability(player, current_pick=1, picks_until_next=10)

    assert conditional > 0.01
    assert conditional < early


def test_need_does_not_boost_negative_vorp_players():
    low_level = {Position.QB: 400.0}
    qb = Player("qb-x", "QB X", Position.QB, projected_points=300)
    player_vorp = vorp(qb, low_level)
    assert player_vorp < 0
    for need in (1.2, 0.55):
        assert max(0.0, player_vorp) * need == 0.0


def test_roster_need_diminishes_after_slots_fill(players, settings):
    rb_players = [player for player in players if player.position == Position.RB]
    empty = roster_need_multiplier(Position.RB, [], settings, 4)
    full = roster_need_multiplier(Position.RB, rb_players[:3], settings, 4)

    assert empty > full


def test_guardrails_suppress_early_kicker(players, settings):
    kicker = next(player for player in players if player.position == Position.K)
    assert guardrail_adjustment(kicker, 20, [], settings, 1) < -30
    assert guardrail_adjustment(kicker, 20, [], settings, settings.rounds) == 0


def test_recommendations_are_deterministic_explainable_and_adjustable(
    players, settings, empty_state
):
    baseline = recommend(players, empty_state, settings, limit=10)
    repeated = recommend(players, empty_state, settings, limit=10)
    faded = recommend(
        players,
        empty_state,
        settings,
        {"qb-1": UserAdjustment("qb-1", tag="avoid")},
        limit=10,
    )

    assert baseline == repeated
    assert baseline[0].breakdown.vorp != 0
    assert baseline[0].reasons
    assert all(item.tier_label in RecommendationLabel for item in baseline)
    assert all(item.player_id != "qb-1" for item in faded)


def test_drafted_players_are_excluded(players, settings, empty_state):
    from dvs_engine import apply_pick

    state = apply_pick(empty_state, "qb-1")
    results = recommend(players, state, settings)

    assert "qb-1" not in {result.player_id for result in results}


def test_formula_params_override_label_thresholds(players, settings, empty_state):
    tuned = LeagueSettings(
        team_count=settings.team_count,
        roster_slots=settings.roster_slots,
        user_team_id=settings.user_team_id,
        formula_params=FormulaParams(cant_pass_vorp_min=999.0),
    )
    baseline = recommend(players, empty_state, tuned, limit=10)
    assert all(item.tier_label != RecommendationLabel.CANT_PASS for item in baseline)


def test_vorp_is_projection_minus_replacement_level():
    player = Player("rb-1", "RB", Position.RB, projected_points=250)
    levels = {Position.RB: 155.0}
    assert vorp(player, levels) == 95.0


def test_replacement_levels_use_worst_player_when_pool_is_thin(settings):
    thin = [
        Player("qb-1", "QB1", Position.QB, projected_points=300, adp=1.0),
        Player("qb-2", "QB2", Position.QB, projected_points=280, adp=2.0),
    ]
    levels = replacement_levels(thin, settings)
    assert levels[Position.QB] == 280


def test_replacement_levels_empty_position_returns_zero(settings):
    levels = replacement_levels([], settings)
    assert levels[Position.QB] == 0.0


def test_tier_cliff_is_zero_without_lower_tier():
    lone_top = Player("wr-1", "WR1", Position.WR, projected_points=250, adp=1.0, tier=1)
    pool = [lone_top]
    assert tier_cliff_urgency(lone_top, pool, 0.2) == 0.0


def test_survival_probability_defaults_when_adp_missing():
    player = Player("x", "X", Position.RB, projected_points=200, adp=None)
    assert survival_probability(player, current_pick=1, picks_until_next=4) == 0.5


def test_survival_probability_respects_custom_params():
    player = Player("x", "X", Position.RB, projected_points=200, adp=50.0)
    params = FormulaParams(survival_default_no_adp=0.25)
    missing = Player("y", "Y", Position.RB, projected_points=200, adp=None)
    assert survival_probability(missing, 1, 4, params) == 0.25
    assert 0.01 <= survival_probability(player, 1, 4, params) <= 0.99


def test_picks_until_team_turn_follows_snake_schedule(settings):
    state = DraftState(settings.team_count)
    assert picks_until_team_turn(state, "1") == settings.team_count * 2 - 1

    state = apply_pick(state, "qb-1")
    assert picks_until_team_turn(state, "1") == settings.team_count * 2 - 2


def test_opponent_demand_factor_scales_with_unfilled_direct_slots(players, settings):
    state = DraftState(settings.team_count)
    player_map = {player.id: player for player in players}
    all_needing = opponent_demand_factor(Position.QB, state, player_map, settings)
    assert all_needing == pytest.approx(1.15)

    partial = apply_pick(apply_pick(state, "qb-1"), "qb-2")
    reduced = opponent_demand_factor(Position.QB, partial, player_map, settings)
    assert reduced < all_needing


def test_effective_player_applies_points_delta_and_tier_override():
    player = Player("rb-1", "RB", Position.RB, projected_points=200, tier=2)
    adjusted = effective_player(
        player, UserAdjustment("rb-1", points_delta=15, tier_override=1)
    )
    assert adjusted.projected_points == 215
    assert adjusted.tier == 1


def test_guardrails_suppress_early_qb_in_one_qb_league(players, settings):
    qb = next(player for player in players if player.id == "qb-1")
    low_vorp = guardrail_adjustment(qb, 10, [], settings, 2)
    high_vorp = guardrail_adjustment(qb, 60, [], settings, 2)
    assert low_vorp < 0
    assert high_vorp == 0


def test_guardrails_penalize_rb_heavy_roster_in_mid_draft(players, settings):
    rb = next(player for player in players if player.id == "rb-1")
    wr = next(player for player in players if player.id == "wr-1")
    rb_heavy = [rb, rb, rb]
    balanced = [rb, wr]
    assert guardrail_adjustment(rb, 30, rb_heavy, settings, 6) < guardrail_adjustment(
        rb, 30, balanced, settings, 6
    )


def test_recommend_score_matches_formula_decomposition(players, settings, empty_state):
    results = recommend(players, empty_state, settings, limit=5)
    top = results[0]
    params = settings.formula_params
    value = max(0.0, top.breakdown.vorp) * top.breakdown.need_multiplier
    expected = (
        value
        + top.breakdown.tier_urgency * params.urgency_weight
        + top.breakdown.guardrail_adjustment
    )
    assert top.dvs_score == pytest.approx(expected, abs=0.01)


def test_my_guy_tag_adds_configurable_bonus(players, settings, empty_state):
    params = FormulaParams(my_guy_bonus=12.0)
    tuned = LeagueSettings(
        team_count=settings.team_count,
        roster_slots=settings.roster_slots,
        user_team_id=settings.user_team_id,
        formula_params=params,
    )
    baseline = recommend(players, empty_state, tuned, limit=20)
    boosted = recommend(
        players,
        empty_state,
        tuned,
        {"rb-1": UserAdjustment("rb-1", tag="myGuy")},
        limit=20,
    )
    baseline_score = next(item for item in baseline if item.player_id == "rb-1").dvs_score
    boosted_score = next(item for item in boosted if item.player_id == "rb-1").dvs_score
    assert boosted_score - baseline_score == 12.0


def test_label_cant_pass_when_high_vorp_and_low_survival():
    urgent_pool = [
        Player(
            id="rb-elite",
            name="Elite RB",
            position=Position.RB,
            projected_points=300,
            adp=10.0,
            tier=1,
        ),
        Player(
            id="rb-repl",
            name="Replacement RB",
            position=Position.RB,
            projected_points=100,
            adp=200.0,
            tier=3,
        ),
    ]
    state = DraftState(team_count=2)
    league = LeagueSettings(
        team_count=2,
        roster_slots={"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
        user_team_id="1",
        formula_params=FormulaParams(cant_pass_survival_max=0.99),
    )
    results = recommend(urgent_pool, state, league, limit=1)
    assert results[0].breakdown.vorp > 20
    assert results[0].tier_label == RecommendationLabel.CANT_PASS


def test_recommend_sorts_by_score_then_adp_then_id():
    tied = [
        Player("z-player", "Z", Position.RB, projected_points=300, adp=5.0, tier=1),
        Player("a-player", "A", Position.RB, projected_points=300, adp=10.0, tier=1),
        Player("m-player", "M", Position.RB, projected_points=100, adp=1.0, tier=3),
    ]
    league = LeagueSettings(
        team_count=2,
        roster_slots={"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
        user_team_id="1",
    )
    state = DraftState(team_count=2)
    results = recommend(tied, state, league, limit=2)
    assert [item.player_id for item in results] == ["z-player", "a-player"]


def test_points_delta_affects_vorp_in_recommendations(players, settings, empty_state):
    baseline = recommend(players, empty_state, settings, limit=20)
    boosted = recommend(
        players,
        empty_state,
        settings,
        {"rb-1": UserAdjustment("rb-1", points_delta=25)},
        limit=20,
    )
    baseline_vorp = next(item for item in baseline if item.player_id == "rb-1").breakdown.vorp
    boosted_vorp = next(item for item in boosted if item.player_id == "rb-1").breakdown.vorp
    assert boosted_vorp - baseline_vorp == 25
