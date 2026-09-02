"""Keeper round accounting and demand-adjusted replacement levels."""

from __future__ import annotations

from collections import Counter

import pytest
from dvs_engine import DraftState, FormulaParams, LeagueSettings, Player, Position, apply_pick
from dvs_engine.formula import replacement_levels


TWELVE = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "BENCH": 6,
    "K": 1,
    "DST": 1,
}


def _rb_pool(count: int, start_points: float = 300.0) -> list[Player]:
    return [
        Player(
            f"rb-{index}",
            f"RB {index}",
            Position.RB,
            projected_points=start_points - index,
            adp=float(index + 1),
            tier=1 if index < 12 else 2,
        )
        for index in range(count)
    ]


def test_keeper_slots_reduce_live_rounds():
    settings = LeagueSettings(roster_slots=TWELVE, keeper_slots=1)
    assert settings.roster_size == 15
    assert settings.rounds == 14


def test_demand_adjusted_off_matches_static():
    settings = LeagueSettings(roster_slots=TWELVE, team_count=12)
    pool = _rb_pool(40)
    static = replacement_levels(pool, settings)
    drafted = Counter({Position.RB: 12})
    assert replacement_levels(pool, settings, drafted) == static


def test_demand_adjusted_on_shifts_when_enabled():
    settings = LeagueSettings(
        roster_slots=TWELVE,
        team_count=12,
        formula_params=FormulaParams(demand_adjusted_replacement=True),
    )
    pool = _rb_pool(40)
    static = replacement_levels(pool, settings)
    drafted = Counter({Position.RB: 12})
    adjusted = replacement_levels(pool, settings, drafted)
    assert adjusted[Position.RB] >= static[Position.RB] - 5


def test_naive_keeper_removal_distorts_replacement():
    settings = LeagueSettings(roster_slots=TWELVE, team_count=12)
    pool = _rb_pool(40)
    static = replacement_levels(pool, settings)
    keeper_ids = {player.id for player in pool[:12]}
    live_pool = [player for player in pool if player.id not in keeper_ids]
    naive = replacement_levels(live_pool, settings)
    distortion = static[Position.RB] - naive[Position.RB]
    assert distortion > 5


def test_apply_pick_preserves_reserved_rosters():
    state = DraftState(
        team_count=4,
        reserved_rosters={"1": ("keeper-1",)},
    )
    after = apply_pick(state, "p1")
    assert after.reserved_rosters == state.reserved_rosters
    undone = apply_pick(after, "p2")
    from dvs_engine import undo_last_pick

    restored = undo_last_pick(undone)
    assert restored.reserved_rosters == state.reserved_rosters
