"""V5 roster policy: negative VORP, bench balance, reliability."""

from __future__ import annotations

import pytest
from dvs_engine import LeagueSettings, Player, Position, V5FormulaParams
from dvs_engine.formula import replacement_levels
from dvs_engine.phase import draft_phase
from dvs_engine.v5_policy import (
    apply_reliability_buckets,
    bench_balance_adjustment,
    compose_guardrail_for_v5,
    compose_shape_for_v5,
    negative_vorp_adjustment,
    raw_reliability_fit,
    roster_risk_score,
    usable_quality_weight,
)


def _params(**overrides) -> V5FormulaParams:
    return V5FormulaParams(**overrides)


def _settings(**overrides) -> LeagueSettings:
    base = {
        "team_count": 12,
        "roster_slots": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "BENCH": 6, "K": 1, "DST": 1},
        "user_team_id": "1",
        "formula_params": _params(),
    }
    base.update(overrides)
    return LeagueSettings(**base)


def test_negative_vorp_separates_mild_and_severe_bench_assets():
    params = _params()
    from dvs_engine.phase import DraftPhase

    phase = DraftPhase(
        progress=1.0,
        starter_completion=1.0,
        late_weight=1.0,
        starter_slots_filled=7,
        starter_slots_total=7,
        open_starter_slots=(),
    )
    replacement = 194.5
    mild_adj = negative_vorp_adjustment(
        Player("rb-good", "Good", Position.RB, projected_points=174.5),
        -20.0,
        replacement,
        phase,
        params,
    )
    severe_adj = negative_vorp_adjustment(
        Player("rb-bad", "Bad", Position.RB, projected_points=79.5),
        -115.0,
        replacement,
        phase,
        params,
    )
    assert mild_adj > severe_adj
    assert (severe_adj - mild_adj) <= -1.5


def test_negative_vorp_zero_when_policy_strength_zero():
    params = _params(v5_policy_strength=0.0)
    settings = _settings(formula_params=params)
    levels = {Position.RB: 194.5}
    roster: list[Player] = []
    phase = draft_phase(roster, settings, levels, params, current_round=14)
    player = Player("rb", "RB", Position.RB, projected_points=80)
    assert negative_vorp_adjustment(player, -114.5, 194.5, phase, params) == 0.0


def test_bench_balance_disabled_without_bench_slots():
    params = _params()
    settings = _settings(roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "BENCH": 0, "K": 1, "DST": 1})
    levels = {Position.RB: 150.0, Position.WR: 150.0}
    roster: list[Player] = []
    phase = draft_phase(roster, settings, levels, params, current_round=14)
    player = Player("rb", "RB", Position.RB, projected_points=120)
    adj, _, _ = bench_balance_adjustment(player, roster, settings, levels, phase, params)
    assert adj == 0.0


def test_reliability_bounded_and_zero_without_close_bucket():
    params = _params()
    fits = {"a": 0.5, "b": 0.4, "c": -0.2}
    scores = {"a": 50.0, "b": 49.0, "c": 40.0}
    adjustments = apply_reliability_buckets(scores, fits, params)
    assert adjustments["a"] == pytest.approx(0.5 * params.v5_policy_strength, abs=0.01)
    assert adjustments["c"] == 0.0
    assert all(abs(value) <= params.reliability_weight_max for value in adjustments.values())


def test_reliability_fit_requires_known_risk():
    params = _params()
    settings = _settings()
    levels = {Position.WR: 150.0, Position.RB: 150.0}
    roster = [
        Player("wr1", "WR1", Position.WR, projected_points=200, risk_score=6.8),
        Player("rb1", "RB1", Position.RB, projected_points=190, risk_score=6.5),
    ]
    phase = draft_phase(roster, settings, levels, params, current_round=14)
    candidate = Player("wr2", "WR2", Position.WR, projected_points=180)
    assert raw_reliability_fit(candidate, roster_risk_score(roster, settings, levels, params), phase, params) == 0.0
    candidate_with_risk = Player("wr2", "WR2", Position.WR, projected_points=180, risk_score=4.0)
    fit = raw_reliability_fit(
        candidate_with_risk,
        roster_risk_score(roster, settings, levels, params),
        phase,
        params,
    )
    assert fit > 0.0


def test_zero_delta_shape_and_guardrail_match_legacy():
    params = _params(v5_policy_strength=0.0)
    settings = _settings(formula_params=params)
    roster = [
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
    ]
    player = Player("rb2", "RB2", Position.RB, projected_points=180)
    levels = replacement_levels([*roster, player], settings)
    vorp_value = player.projected_points - levels[Position.RB]
    from dvs_engine.v4 import shape_adjustment
    from dvs_engine.formula import guardrail_adjustment

    legacy_shape = shape_adjustment(Position.RB, roster, settings, 8, params)
    legacy_guard = guardrail_adjustment(player, vorp_value, roster, settings, 8)
    assert compose_shape_for_v5(Position.RB, roster, settings, 8, params, 1.0) == pytest.approx(legacy_shape)
    assert compose_guardrail_for_v5(player, vorp_value, roster, settings, 8, params, 1.0) == pytest.approx(legacy_guard)


def test_usable_quality_weight_floors_sub_replacement():
    params = _params()
    player = Player("rb", "RB", Position.RB, projected_points=100)
    weight = usable_quality_weight(player, {Position.RB: 200.0}, params)
    assert weight == 0.0
    near = Player("rb2", "RB2", Position.RB, projected_points=190)
    near_weight = usable_quality_weight(near, {Position.RB: 200.0}, params)
    assert 0.0 < near_weight < 1.0
