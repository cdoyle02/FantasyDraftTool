import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    RecommendationLabel,
    UserAdjustment,
    recommend,
)


def _v3_league() -> LeagueSettings:
    return LeagueSettings(
        team_count=4,
        roster_slots={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1, "BENCH": 2},
        user_team_id="1",
        formula_params=FormulaParams(formula_version=3),
    )


def test_formula_params_default_to_version_4():
    assert FormulaParams().formula_version == 4
    with pytest.raises(ValueError, match="1, 2, 3, or 4"):
        FormulaParams(formula_version=5)


def test_v3_score_matches_need_weighted_decomposition(players, empty_state):
    settings = _v3_league()
    results = recommend(players, empty_state, settings, limit=5)
    top = results[0]
    params = settings.formula_params
    base = top.breakdown.marginal_value + params.wait_loss_weight * top.breakdown.wait_loss
    expected = base * top.breakdown.need_multiplier + top.breakdown.guardrail_adjustment
    assert top.dvs_score == pytest.approx(expected, abs=0.01)
    assert top.breakdown.need_multiplier != 1.0


def test_v3_dispatch_differs_from_v1_and_v2(players, empty_state):
    shared = dict(
        team_count=4,
        roster_slots={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1, "BENCH": 2},
        user_team_id="1",
    )
    v1 = recommend(
        players,
        empty_state,
        LeagueSettings(**shared, formula_params=FormulaParams(formula_version=1)),
        limit=3,
    )
    v2 = recommend(
        players,
        empty_state,
        LeagueSettings(**shared, formula_params=FormulaParams(formula_version=2)),
        limit=3,
    )
    v3 = recommend(
        players,
        empty_state,
        LeagueSettings(**shared, formula_params=FormulaParams()),
        limit=3,
    )
    assert v1[0].breakdown.marginal_value == 0.0
    assert v2[0].breakdown.need_multiplier == 1.0
    assert v3[0].breakdown.need_multiplier != 1.0
    assert v3[0].dvs_score != v2[0].dvs_score


def test_v3_labels_use_wait_loss_thresholds():
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


def test_v3_my_guy_bonus_still_applies(players, empty_state):
    params = FormulaParams(my_guy_bonus=12.0)
    league = LeagueSettings(
        team_count=4,
        roster_slots={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1, "BENCH": 2},
        user_team_id="1",
        formula_params=params,
    )
    baseline = recommend(players, empty_state, league, limit=20)
    boosted = recommend(
        players,
        empty_state,
        league,
        {"rb-1": UserAdjustment("rb-1", tag="myGuy")},
        limit=20,
    )
    baseline_score = next(item for item in baseline if item.player_id == "rb-1").dvs_score
    boosted_score = next(item for item in boosted if item.player_id == "rb-1").dvs_score
    assert boosted_score - baseline_score == pytest.approx(12.0)
