"""Lineup-aware starter completion for V4.1 phase weighting."""

from __future__ import annotations

import pytest
from dvs_engine import FormulaParams, LeagueSettings, Player, Position
from dvs_engine.formula import position_caps_map, replacement_levels
from dvs_engine.lineup import starter_slot_fill
from dvs_engine.phase import draft_phase, player_fills_open_starter


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


def _levels() -> dict[Position, float]:
    settings = LeagueSettings(roster_slots=TWELVE)
    levels = replacement_levels([], settings)
    return {
        **levels,
        Position.QB: 200.0,
        Position.RB: 150.0,
        Position.WR: 150.0,
        Position.TE: 120.0,
    }


def test_flex_empty_gives_six_of_seven_completion():
    settings = LeagueSettings(roster_slots=TWELVE)
    levels = _levels()
    roster = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
    ]
    fill = starter_slot_fill(roster, settings, levels)
    assert fill.total == 7
    assert fill.filled == 6
    assert fill.filled / fill.total == pytest.approx(6 / 7)
    assert "FLEX" in fill.open_slots


def test_flex_eligible_player_completes_roster():
    settings = LeagueSettings(roster_slots=TWELVE)
    levels = _levels()
    base = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
    ]
    fill_before = starter_slot_fill(base, settings, levels)
    fill_after = starter_slot_fill(
        [*base, Player("rb3", "RB3", Position.RB, projected_points=180)],
        settings,
        levels,
    )
    assert fill_before.filled == 6
    assert fill_after.filled == 7
    assert fill_after.filled / fill_after.total == pytest.approx(1.0)


def test_k_dst_do_not_affect_starter_completion():
    settings = LeagueSettings(roster_slots=TWELVE)
    levels = _levels()
    full_starters = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
        Player("rb3", "RB3", Position.RB, projected_points=180),
    ]
    with_special = [*full_starters, Player("k", "K", Position.K, projected_points=130)]
    assert starter_slot_fill(full_starters, settings, levels) == starter_slot_fill(
        with_special, settings, levels
    )


def test_superflex_qb_fills_open_slot():
    slots = {**TWELVE, "SUPERFLEX": 1}
    settings = LeagueSettings(roster_slots=slots)
    levels = _levels()
    roster = [
        Player("qb1", "QB1", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
        Player("rb3", "RB3", Position.RB, projected_points=180),
    ]
    fill = starter_slot_fill(roster, settings, levels)
    assert "SUPERFLEX" in fill.open_slots
    qb2 = Player("qb2", "QB2", Position.QB, projected_points=260)
    assert player_fills_open_starter(qb2, fill.open_slots)
    k = Player("k", "K", Position.K, projected_points=130)
    assert not player_fills_open_starter(k, fill.open_slots)
    fill_with_qb = starter_slot_fill([*roster, qb2], settings, levels)
    assert fill_with_qb.filled == fill_with_qb.total


def test_late_weight_increases_with_progress_and_completion():
    settings = LeagueSettings(roster_slots=TWELVE)
    levels = _levels()
    params = FormulaParams()
    caps = position_caps_map(settings)
    empty = draft_phase([], settings, levels, params, 1, caps)
    late_empty = draft_phase([], settings, levels, params, settings.rounds, caps)
    assert late_empty.late_weight > empty.late_weight
    full = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
        Player("rb3", "RB3", Position.RB, projected_points=180),
    ]
    partial = full[:-1]
    late_partial = draft_phase(partial, settings, levels, params, settings.rounds, caps)
    late_full = draft_phase(full, settings, levels, params, settings.rounds, caps)
    assert late_full.late_weight >= late_partial.late_weight
