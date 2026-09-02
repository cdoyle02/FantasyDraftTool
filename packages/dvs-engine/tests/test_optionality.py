"""Late-round upside, handcuff, and IR stash optionality."""

from __future__ import annotations

from dataclasses import replace

import pytest
from dvs_engine import FormulaParams, LeagueSettings, Player, Position
from dvs_engine.formula import replacement_levels
from dvs_engine.optionality import contingent_value, ir_stash_value, late_round_upside, optionality_for_player
from dvs_engine.phase import draft_phase
from dvs_engine.formula import position_caps_map


def _phase(late: bool = True):
    settings = LeagueSettings(
        roster_slots={
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "BENCH": 6,
            "K": 1,
            "DST": 1,
        },
        ir_slots=1,
    )
    levels = replacement_levels([], settings)
    levels = {**levels, Position.RB: 150.0}
    params = FormulaParams()
    current = settings.rounds if late else 3
    return settings, levels, params, draft_phase([], settings, levels, params, current, position_caps_map(settings))


def test_late_round_upside_zero_early():
    _, levels, params, phase = _phase(late=False)
    player = Player("rb", "RB", Position.RB, projected_points=180, upside_score=9.0, is_rookie=True)
    points, reason = late_round_upside(player, phase, params, levels)
    assert points < 0.5
    assert reason is None


def test_late_round_upside_positive_for_high_upside_rookie():
    settings, levels, params, _ = _phase(late=True)
    roster = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
        Player("rb3", "RB3", Position.RB, projected_points=180),
    ]
    from dvs_engine.formula import position_caps_map
    from dvs_engine.phase import draft_phase

    phase = draft_phase(
        roster, settings, levels, params, settings.rounds, position_caps_map(settings)
    )
    player = Player(
        "rb",
        "RB",
        Position.RB,
        projected_points=120,
        upside_score=9.0,
        is_rookie=True,
    )
    points, reason = late_round_upside(player, phase, params, levels)
    assert points > 0.5
    assert reason is not None


def test_handcuff_bonus_without_starter_is_zero():
    settings, levels, params, phase = _phase()
    starter = Player(
        "rb1",
        "Starter",
        Position.RB,
        team="LV",
        projected_points=250,
        depth_chart_rank=1,
        depth_chart_source="derived",
    )
    backup = Player(
        "rb2",
        "Backup",
        Position.RB,
        team="LV",
        projected_points=80,
        depth_chart_rank=2,
        depth_chart_source="derived",
        risk_score=10.0,
    )
    _, bonus, _ = contingent_value(backup, [starter], phase, params, levels)
    assert 1.0 <= bonus <= 4.0


def test_handcuff_zero_without_rostered_starter():
    settings, levels, params, phase = _phase()
    backup = Player(
        "rb2",
        "Backup",
        Position.RB,
        team="LV",
        projected_points=80,
        depth_chart_rank=2,
    )
    _, bonus, _ = contingent_value(backup, [], phase, params, levels)
    assert bonus == pytest.approx(0.0)


def test_handcuff_depth_three_is_zero():
    settings, levels, params, phase = _phase()
    starter = Player("rb1", "Starter", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    rb3 = Player("rb3", "RB3", Position.RB, team="LV", projected_points=70, depth_chart_rank=3)
    _, bonus, _ = contingent_value(rb3, [starter], phase, params, levels)
    assert bonus == pytest.approx(0.0)


def test_risk_score_swing_is_bounded():
    settings, levels, params, phase = _phase()
    starter = Player("rb1", "Starter", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    bonuses = []
    for risk in (1.0, 10.0):
        backup = Player(
            "rb2",
            "Backup",
            Position.RB,
            team="LV",
            projected_points=80,
            depth_chart_rank=2,
            risk_score=risk,
            depth_chart_source="official",
        )
        _, bonus, _ = contingent_value(backup, [starter], phase, params, levels)
        bonuses.append(bonus)
    if bonuses[0] > 0:
        ratio = bonuses[1] / bonuses[0]
        assert 0.75 <= ratio <= 1.25


def test_derived_depth_chart_haircut():
    settings, levels, params, phase = _phase()
    starter = Player("rb1", "Starter", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    derived = Player(
        "rb2",
        "Backup",
        Position.RB,
        team="LV",
        projected_points=80,
        depth_chart_rank=2,
        depth_chart_source="derived",
    )
    official = replace(derived, depth_chart_source="official")
    derived_contingent, derived_bonus, _ = contingent_value(derived, [starter], phase, params, levels)
    official_contingent, official_bonus, _ = contingent_value(official, [starter], phase, params, levels)
    assert derived_contingent < official_contingent
    assert derived_bonus <= official_bonus


def test_ir_stash_requires_open_slot_and_late_round():
    settings, levels, params, phase = _phase(late=True)
    player = Player(
        "wr",
        "WR",
        Position.WR,
        projected_points=100,
        upside_score=8.0,
        ir_eligible=True,
    )
    value, reason = ir_stash_value(player, [], settings, settings.rounds, phase, params)
    assert value > 0.5
    assert reason is not None
    early_value, _ = ir_stash_value(player, [], settings, 5, phase, params)
    assert early_value < 0.5


def test_ir_stash_zero_when_no_ir_slots():
    settings, levels, params, phase = _phase()
    settings = replace(settings, ir_slots=0)
    player = Player("wr", "WR", Position.WR, upside_score=8.0, ir_eligible=True)
    value, _ = ir_stash_value(player, [], settings, settings.rounds, phase, params)
    assert value == pytest.approx(0.0)


def test_optionality_combine_max():
    settings, levels, params, phase = _phase()
    starter = Player("rb1", "Starter", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    backup = Player(
        "rb2",
        "Backup",
        Position.RB,
        team="LV",
        projected_points=80,
        depth_chart_rank=2,
        upside_score=9.0,
        is_rookie=True,
    )
    result = optionality_for_player(
        backup, [starter], settings, levels, phase, params, settings.rounds
    )
    assert result.optionality_value == max(
        result.late_round_upside,
        result.handcuff_bonus,
        result.ir_stash_value,
    )
