"""K/DST eligibility, caps, and candidate-conditioned lookahead."""

from __future__ import annotations

import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    apply_pick,
    recommend_v4,
)
from dvs_engine.lineup import marginal_value
from dvs_engine.special_teams import is_special_teams_eligible, special_teams_status
from dvs_engine.formula import position_caps_map, replacement_levels


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


def _league(**overrides) -> LeagueSettings:
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


def test_second_kicker_marginal_is_zero_at_cap():
    settings = _league()
    params = settings.formula_params
    caps = position_caps_map(settings)
    levels = replacement_levels([], settings)
    levels = {**levels, Position.K: 100.0}
    k1 = Player("k-1", "K1", Position.K, projected_points=130, adp=150.0)
    k2 = Player("k-2", "K2", Position.K, projected_points=128, adp=151.0)
    roster = [k1]
    assert marginal_value(k2, roster, settings, levels, params, caps) == pytest.approx(0.0)


def test_k2_blocked_at_cap_even_in_final_round():
    settings = _league()
    params = settings.formula_params
    k1 = Player("k-1", "K1", Position.K, projected_points=130)
    k2 = Player("k-2", "K2", Position.K, projected_points=128)
    status = special_teams_status(k2, [k1], settings, settings.rounds, params)
    assert status.cap_blocked
    assert not is_special_teams_eligible(k2, [k1], settings, settings.rounds, params)


def test_kicker_eligible_only_in_final_round_by_default():
    settings = _league()
    params = settings.formula_params
    k = Player("k-1", "K", Position.K, projected_points=130)
    dst = Player("dst-1", "DST", Position.DST, projected_points=125)
    roster = [dst]
    assert not is_special_teams_eligible(k, roster, settings, 13, params)
    assert is_special_teams_eligible(k, roster, settings, 15, params)


def test_dst_eligible_in_final_two_rounds():
    settings = _league()
    params = settings.formula_params
    dst = Player("dst-1", "DST", Position.DST, projected_points=125)
    assert not is_special_teams_eligible(dst, [], settings, 13, params)
    assert is_special_teams_eligible(dst, [], settings, 14, params)
    assert is_special_teams_eligible(dst, [], settings, 15, params)


def test_k_two_slot_league_allows_second_kicker():
    slots = {**TWELVE_SLOTS, "K": 2}
    settings = _league(roster_slots=slots)
    params = settings.formula_params
    k1 = Player("k-1", "K1", Position.K, projected_points=130)
    k2 = Player("k-2", "K2", Position.K, projected_points=128)
    assert is_special_teams_eligible(k2, [k1], settings, settings.rounds, params)


def test_dst_run_does_not_raise_wait_loss_or_tier():
    dst = Player("dst-1", "DST", Position.DST, projected_points=125, adp=50.0, tier=1)
    dst2 = Player("dst-2", "DST2", Position.DST, projected_points=120, adp=51.0, tier=1)
    pool = [dst, dst2] + _fillers(30)
    settings = _league()
    state = DraftState(team_count=12)
    for pick in range(1, 50):
        if pick <= len(pool):
            state = apply_pick(state, pool[pick - 1].id if pick <= 2 else f"fill-{pick}")
    results = recommend_v4(pool, state, settings, limit=5)
    dst_results = [item for item in results if item.position == Position.DST]
    for result in dst_results:
        assert result.breakdown.wait_loss == pytest.approx(0.0)
        assert result.breakdown.tier_opportunity_cost == pytest.approx(0.0)


def test_timing_penalty_when_hard_gate_disabled():
    settings = _league(
        formula_params=FormulaParams(special_teams_hard_gate=False),
    )
    k = Player("k-1", "K", Position.K, projected_points=130)
    status = special_teams_status(k, [], settings, 1, settings.formula_params)
    assert status.timing_blocked
    assert status.timing_penalty < 0
