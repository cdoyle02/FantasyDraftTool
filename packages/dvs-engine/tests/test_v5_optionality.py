"""V5 own-handcuff classification and league scaling."""

from __future__ import annotations

import pytest
from dvs_engine import LeagueSettings, Player, Position, V5FormulaParams
from dvs_engine.v5_optionality import (
    adjust_handcuff_bonus,
    count_rostered_own_handcuffs,
    is_own_handcuff_candidate,
    league_handcuff_multiplier,
    optionality_for_player_v5,
    own_handcuff_count_multiplier,
)
from dvs_engine.phase import draft_phase
from dvs_engine.formula import replacement_levels


def _params(**overrides) -> V5FormulaParams:
    return V5FormulaParams(**overrides)


def _levels(*players: Player):
    settings = LeagueSettings(
        team_count=12,
        roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "BENCH": 6, "K": 1, "DST": 1},
        user_team_id="1",
        formula_params=_params(),
    )
    return replacement_levels(list(players), settings)


def test_own_handcuff_requires_rank_one_starter():
    starter = Player("rb1", "S1", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    backup = Player("rb2", "B1", Position.RB, team="LV", projected_points=80, depth_chart_rank=2)
    levels = _levels(starter, backup)
    params = _params()
    is_own, matched = is_own_handcuff_candidate(backup, [starter], levels, params)
    assert is_own
    assert matched is starter


def test_missing_depth_rank_blocks_own_handcuff():
    starter = Player("rb1", "S1", Position.RB, team="LV", projected_points=250)
    backup = Player("rb2", "B1", Position.RB, team="LV", projected_points=80, depth_chart_rank=2)
    levels = _levels(starter, backup)
    params = _params()
    assert not is_own_handcuff_candidate(backup, [starter], levels, params)[0]


def test_external_rb2_is_not_own_handcuff():
    external = Player("rb-x", "Ext", Position.RB, team="DAL", projected_points=90, depth_chart_rank=2)
    levels = _levels(external)
    params = _params()
    assert not is_own_handcuff_candidate(external, [], levels, params)[0]
    raw, adjusted, count, mult, reason = adjust_handcuff_bonus(
        external,
        [],
        LeagueSettings(team_count=8, roster_slots={"RB": 2, "WR": 2, "BENCH": 4}, user_team_id="1", formula_params=_params()),
        levels,
        raw_bonus=6.0,
        params=_params(),
    )
    assert raw == adjusted == 6.0
    assert count == 0
    assert mult == 1.0
    assert reason is None


@pytest.mark.parametrize(
    ("teams", "expected"),
    [(8, 0.45), (10, 0.725), (12, 1.0), (14, 1.10), (16, 1.10), (6, 0.45)],
)
def test_league_handcuff_interpolation(teams: int, expected: float):
    assert league_handcuff_multiplier(teams, _params()) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("existing", "expected"),
    [(0, 1.0), (1, 0.40), (2, 0.20), (3, 0.05)],
)
def test_count_multipliers(existing: int, expected: float):
    assert own_handcuff_count_multiplier(existing, _params()) == expected


def test_second_own_handcuff_diminishing():
    starter = Player("rb1", "S1", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    first = Player("rb2", "B1", Position.RB, team="LV", projected_points=80, depth_chart_rank=2)
    second = Player("rb3", "B2", Position.RB, team="KC", projected_points=75, depth_chart_rank=2)
    starter2 = Player("rb4", "S2", Position.RB, team="KC", projected_points=240, depth_chart_rank=1)
    roster = [starter, first, starter2]
    levels = _levels(starter, first, second, starter2)
    settings = LeagueSettings(team_count=12, roster_slots={"RB": 2, "WR": 2, "BENCH": 4}, user_team_id="1", formula_params=_params())
    assert count_rostered_own_handcuffs(roster, levels, _params()) == 1
    _, adjusted, count, _, _ = adjust_handcuff_bonus(second, roster, settings, levels, 10.0, _params())
    assert count == 1
    assert adjusted == pytest.approx(10.0 * 0.40, rel=0.01)


def test_zero_policy_strength_preserves_raw_handcuff():
    starter = Player("rb1", "S1", Position.RB, team="LV", projected_points=250, depth_chart_rank=1)
    backup = Player("rb2", "B1", Position.RB, team="LV", projected_points=80, depth_chart_rank=2)
    levels = _levels(starter, backup)
    settings = LeagueSettings(team_count=8, roster_slots={"RB": 2, "WR": 2, "BENCH": 4}, user_team_id="1", formula_params=_params(v5_policy_strength=0.0))
    _, adjusted, _, _, reason = adjust_handcuff_bonus(backup, [starter], settings, levels, 8.0, settings.formula_params)
    assert adjusted == 8.0
    assert reason is None
