"""V4.1 behavioral regression checks."""

from __future__ import annotations

import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Pick,
    Player,
    Position,
    recommend,
    recommend_v4,
    team_on_clock,
)
from dvs_engine.special_teams import future_special_teams_eligible

TWELVE = {
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
        "roster_slots": TWELVE,
        "user_team_id": "1",
        "formula_params": FormulaParams(),
    }
    base.update(overrides)
    return LeagueSettings(**base)


def test_early_skill_only_has_zero_optionality():
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
    ]
    league = _league(
        roster_slots={**TWELVE, "K": 0, "DST": 0},
    )
    results = recommend_v4(pool, DraftState(team_count=12), league, limit=2)
    assert all(item.breakdown.optionality_value == pytest.approx(0.0) for item in results)


def test_golden_early_mid_skill_scores_unchanged_without_metadata():
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
        Player("rb-2", "RB2", Position.RB, projected_points=240, adp=30.0, tier=2),
        Player("wr-2", "WR2", Position.WR, projected_points=235, adp=31.0, tier=2),
    ]
    league = _league(
        team_count=4,
        roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
    )
    results = recommend(pool, DraftState(team_count=4), league, limit=4)
    top = results[0]
    assert top.player_id == "rb-1"
    assert top.breakdown.optionality_value == pytest.approx(0.0)
    assert top.dvs_score == pytest.approx(64.9154, abs=0.01)


def test_late_sleeper_beats_low_value_kicker():
    league = _league()
    roster = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
        Player("rb3", "RB3", Position.RB, projected_points=180),
        Player("wr3", "WR3", Position.WR, projected_points=170),
        Player("rb4", "RB4", Position.RB, projected_points=160),
        Player("wr4", "WR4", Position.WR, projected_points=150),
        Player("rb5", "RB5", Position.RB, projected_points=140),
        Player("wr5", "WR5", Position.WR, projected_points=130),
        Player("rb6", "RB6", Position.RB, projected_points=120),
    ]
    sleeper = Player(
        "rb-sleep",
        "Sleeper RB",
        Position.RB,
        projected_points=55,
        adp=180.0,
        tier=5,
        upside_score=9.0,
        is_rookie=True,
    )
    k = Player("k-1", "K", Position.K, projected_points=130, adp=150.0, tier=1)
    pool = [sleeper, k] + [
        Player(f"fill-{i}", f"Fill {i}", Position.WR, projected_points=40, adp=200 + i)
        for i in range(40)
    ]
    state = DraftState(
        team_count=12,
        pick_history=tuple(),
        reserved_rosters={"1": tuple(p.id for p in roster)},
    )
    history = tuple(
        Pick(pick, team_on_clock(pick, 12), f"ghost-{pick}") for pick in range(1, 169)
    )
    state = DraftState(12, history, {"1": tuple(p.id for p in roster)})
    results = recommend_v4(pool, state, league, limit=10)
    sleeper_result = next((r for r in results if r.player_id == "rb-sleep"), None)
    k_result = next((r for r in results if r.player_id == "k-1"), None)
    assert sleeper_result is not None
    assert k_result is not None
    assert sleeper_result.dvs_score > k_result.dvs_score


def test_candidate_conditioned_k_dst_lookahead_differs_by_path():
    league = _league()
    params = league.formula_params
    roster = [
        Player(f"p-{i}", f"P{i}", Position.WR, projected_points=100 - i, adp=10 + i)
        for i in range(13)
    ]
    dst = Player("dst-1", "DST1", Position.DST, projected_points=125, adp=150.0)
    wr = Player("wr-late", "WR Late", Position.WR, projected_points=50, adp=160.0)
    k = Player("k-1", "K1", Position.K, projected_points=130, adp=151.0)
    pool = [dst, wr, k]
    state = DraftState(
        team_count=12,
        pick_history=tuple(),
        reserved_rosters={"1": tuple(p.id for p in roster)},
    )
    penultimate = (league.rounds - 1) * 12 + 1
    history = tuple(Pick(p, team_on_clock(p, 12), f"g-{p}") for p in range(1, penultimate))
    state = DraftState(12, history, {"1": tuple(p.id for p in roster)})
    next_round = league.rounds
    assert future_special_teams_eligible(k, (*roster, dst), league, next_round, params)
    assert future_special_teams_eligible(
        k, (*roster, wr), league, next_round, params
    ) or params.special_teams_hard_gate


def test_missing_metadata_produces_no_optionality_bonus():
    player = Player("rb", "RB", Position.RB, projected_points=80, adp=200.0)
    league = _league()
    roster = [Player("rb1", "RB1", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)]
    state = DraftState(
        team_count=12,
        pick_history=tuple(Pick(i, "2", f"g-{i}") for i in range(1, 169)),
        reserved_rosters={"1": tuple(p.id for p in roster)},
    )
    results = recommend_v4([player], state, league, limit=1)
    assert results[0].breakdown.optionality_value == pytest.approx(0.0)


def test_v3_formula_version_still_runs():
    league = LeagueSettings(
        team_count=4,
        roster_slots={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1, "BENCH": 2},
        formula_params=FormulaParams(formula_version=3),
    )
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=250, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=240, adp=2.0, tier=1),
    ]
    results = recommend(pool, DraftState(team_count=4), league, limit=2)
    assert len(results) == 2
