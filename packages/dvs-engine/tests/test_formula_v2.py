import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    RecommendationLabel,
    UserAdjustment,
    marginal_value,
    recommend,
    replacement_levels,
    roster_utility,
    wait_loss,
)
from dvs_engine.formula import survival_probability


def test_roster_utility_assigns_starters_before_bench(settings):
    levels = replacement_levels([], settings)
    levels = {**levels, Position.RB: 150.0, Position.WR: 150.0}
    rb = Player("rb-1", "RB1", Position.RB, projected_points=250)
    wr = Player("wr-1", "WR1", Position.WR, projected_points=240)
    utility = roster_utility([rb, wr], settings, levels, FormulaParams())
    assert utility == pytest.approx(190.0)


def test_marginal_value_reflects_open_starter_slot(settings):
    levels = replacement_levels([], settings)
    levels = {**levels, Position.RB: 150.0, Position.WR: 150.0}
    rb = Player("rb-1", "RB1", Position.RB, projected_points=250)
    wr = Player("wr-1", "WR1", Position.WR, projected_points=240)
    empty = marginal_value(rb, [], settings, levels, FormulaParams())
    with_wr = marginal_value(rb, [wr], settings, levels, FormulaParams())
    assert empty == 100.0
    assert with_wr == 100.0


def test_wait_loss_equals_marginal_when_no_same_position_alternatives():
    rb = Player("rb-1", "RB1", Position.RB, projected_points=250, adp=1.0)
    marginals = {"rb-1": 100.0}
    survival = {"rb-1": 0.5}
    assert wait_loss(rb, [rb], marginals, survival) == 100.0


def test_wait_loss_falls_when_a_likely_fallback_exists(settings):
    elite = Player("rb-1", "RB1", Position.RB, projected_points=250, adp=1.0)
    backup = Player("rb-2", "RB2", Position.RB, projected_points=220, adp=200.0)
    params = FormulaParams()
    marginals = {
        "rb-1": 100.0,
        "rb-2": 70.0,
    }
    survival = {
        player.id: survival_probability(player, 1, 8, params)
        for player in (elite, backup)
    }
    alone = wait_loss(elite, [elite], marginals, survival)
    with_backup = wait_loss(elite, [elite, backup], marginals, survival)
    assert alone > with_backup
    assert with_backup > 0


def test_v2_score_matches_marginal_plus_wait_loss(settings, empty_state, players):
    results = recommend(players, empty_state, settings, limit=5)
    top = results[0]
    params = settings.formula_params
    expected = (
        top.breakdown.marginal_value
        + params.wait_loss_weight * top.breakdown.wait_loss
        + top.breakdown.guardrail_adjustment
    )
    assert top.dvs_score == pytest.approx(expected, abs=0.01)
    assert top.breakdown.need_multiplier == 1.0


def test_v2_labels_use_wait_loss_thresholds():
    pool = [
        Player("rb-elite", "Elite", Position.RB, projected_points=300, adp=10.0, tier=1),
        Player("rb-back", "Back", Position.RB, projected_points=100, adp=200.0, tier=3),
    ]
    league = LeagueSettings(
        team_count=2,
        roster_slots={"QB": 0, "RB": 1, "WR": 0, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
        user_team_id="1",
        formula_params=FormulaParams(value_min=1.0, urgent_wait_loss=0.0),
    )
    results = recommend(pool, DraftState(team_count=2), league, limit=1)
    assert results[0].tier_label == RecommendationLabel.CANT_PASS


def test_avoid_tag_excludes_player_from_v2_recommendations(settings, empty_state, players):
    results = recommend(
        players,
        empty_state,
        settings,
        {"qb-1": UserAdjustment("qb-1", tag="avoid")},
        limit=20,
    )
    assert all(item.player_id != "qb-1" for item in results)


def test_v1_formula_version_preserves_legacy_scoring(settings, empty_state, players):
    v1 = LeagueSettings(
        team_count=settings.team_count,
        roster_slots=settings.roster_slots,
        user_team_id=settings.user_team_id,
        formula_params=FormulaParams(formula_version=1),
    )
    results = recommend(players, empty_state, v1, limit=5)
    top = results[0]
    assert top.breakdown.marginal_value == 0.0
    assert top.breakdown.wait_loss == 0.0
    assert top.breakdown.need_multiplier != 1.0 or top.breakdown.vorp <= 0
