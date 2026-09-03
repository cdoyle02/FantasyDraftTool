"""Formula V5 dispatch, parameter parsing, and zero-delta parity."""

from __future__ import annotations

import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    V5FormulaParams,
    as_jsonable,
    formula_params_from_dict,
    recommend,
    recommend_v4,
    recommend_v5,
)

from v4_golden_helpers import (
    TWELVE,
    V5_ONLY_BREAKDOWN_KEYS,
    _advance_user_picks,
    _fillers,
    _league,
    build_golden_states,
    project_v4_breakdown,
)

GOLDEN_SCENARIO_NAMES = (
    "early_round",
    "mid_round",
    "starters_nearly_complete",
    "late_round",
    "own_handcuff",
    "special_teams_window",
)


def _zero_delta_settings(base: LeagueSettings) -> LeagueSettings:
    params = V5FormulaParams(v5_policy_strength=0.0)
    return LeagueSettings(
        team_count=base.team_count,
        roster_slots=dict(base.roster_slots),
        user_team_id=base.user_team_id,
        scoring_format=base.scoring_format,
        league_type=base.league_type,
        keeper_slots=base.keeper_slots,
        ir_slots=base.ir_slots,
        formula_params=params,
    )


def _project_result(result) -> dict:
    breakdown = project_v4_breakdown(as_jsonable(result.breakdown))
    return {
        "player_id": result.player_id,
        "dvs_score": result.dvs_score,
        "tier_label": result.tier_label.value,
        "reasons": list(result.reasons),
        "breakdown": breakdown,
    }


def test_formula_params_defaults():
    assert FormulaParams().formula_version == 4
    assert V5FormulaParams().formula_version == 5


def test_formula_params_from_dict_version_selection():
    assert isinstance(formula_params_from_dict(None), FormulaParams)
    assert isinstance(formula_params_from_dict({"formulaVersion": 4}), FormulaParams)
    assert isinstance(formula_params_from_dict({"formula_version": 4}), FormulaParams)
    assert isinstance(formula_params_from_dict({"formulaVersion": 5}), V5FormulaParams)
    assert formula_params_from_dict({"formulaVersion": 5}).v5_policy_strength == 1.0


def test_formula_params_rejects_unsupported_version_on_base_type():
    with pytest.raises(ValueError, match="1, 2, 3, or 4"):
        FormulaParams(formula_version=5)


def test_v5_formula_params_validates_policy_strength():
    with pytest.raises(ValueError, match="v5_policy_strength"):
        V5FormulaParams(v5_policy_strength=1.5)


def test_recommend_dispatches_v5():
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
    ]
    league = LeagueSettings(
        team_count=4,
        roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
        user_team_id="1",
        formula_params=V5FormulaParams(),
    )
    results = recommend(pool, DraftState(team_count=4), league, limit=2)
    assert hasattr(results[0].breakdown, "negative_vorp_adjustment")
    assert results[0].breakdown.v5_policy_strength == 1.0


@pytest.mark.parametrize("name", GOLDEN_SCENARIO_NAMES)
def test_zero_delta_v5_matches_v4(name: str):
    live = build_golden_states()[name]
    v4_results = live["recommendations"]
    # Re-run with explicit V4 and zero-delta V5 using same builders.
    from dvs_engine import Pick, team_on_clock

    if name == "early_round":
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
        state = DraftState(team_count=4)
        limit = 4
    elif name == "mid_round":
        pool = _fillers(220) + [
            Player("qb-1", "QB1", Position.QB, projected_points=280, adp=55.0, tier=2),
            Player("rb-mid", "RB Mid", Position.RB, projected_points=240, adp=60.0, tier=2),
            Player("wr-mid", "WR Mid", Position.WR, projected_points=230, adp=61.0, tier=2),
        ]
        league = _league()
        state = _advance_user_picks(pool, ("qb-1", "rb-mid", "wr-mid"))
        limit = 10
    elif name == "starters_nearly_complete":
        starter_roster = [
            Player("qb", "QB", Position.QB, projected_points=280),
            Player("rb1", "RB1", Position.RB, projected_points=250),
            Player("rb2", "RB2", Position.RB, projected_points=240),
            Player("wr1", "WR1", Position.WR, projected_points=230),
            Player("wr2", "WR2", Position.WR, projected_points=220),
            Player("te", "TE", Position.TE, projected_points=200),
        ]
        pool = _fillers(220) + [
            Player("flex-a", "Flex A", Position.RB, projected_points=180, adp=100.0, tier=3),
            Player("flex-b", "Flex B", Position.WR, projected_points=175, adp=101.0, tier=3),
        ]
        league = _league()
        state = DraftState(
            team_count=12,
            pick_history=tuple(Pick(pick, team_on_clock(pick, 12), f"ghost-{pick}") for pick in range(1, 72)),
            reserved_rosters={"1": tuple(p.id for p in starter_roster)},
        )
        limit = 10
    elif name == "late_round":
        late_roster = [
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
            "rb-sleep", "Sleeper RB", Position.RB, projected_points=55, adp=180.0, tier=5,
            upside_score=9.0, is_rookie=True,
        )
        pool = [sleeper] + _fillers(40)
        league = _league()
        state = DraftState(
            team_count=12,
            pick_history=tuple(Pick(pick, team_on_clock(pick, 12), f"ghost-{pick}") for pick in range(1, 169)),
            reserved_rosters={"1": tuple(p.id for p in late_roster)},
        )
        limit = 10
    elif name == "own_handcuff":
        hc_starter = Player(
            "rb1", "Starter", Position.RB, team="LV", projected_points=250,
            depth_chart_rank=1, depth_chart_source="official",
        )
        hc_backup = Player(
            "rb2", "Backup", Position.RB, team="LV", projected_points=80, adp=200.0, tier=5,
            depth_chart_rank=2, depth_chart_source="official", risk_score=6.0,
        )
        pool = [hc_starter, hc_backup, *_fillers(40)]
        league = LeagueSettings(
            team_count=12, roster_slots=TWELVE, user_team_id="1", ir_slots=1,
            formula_params=FormulaParams(),
        )
        state = DraftState(
            team_count=12,
            pick_history=tuple(Pick(i, "2", f"g-{i}") for i in range(1, 169)),
            reserved_rosters={"1": ("rb1",)},
        )
        limit = 5
    else:
        st_roster = [
            Player(f"p-{i}", f"P{i}", Position.WR, projected_points=100 - i, adp=10 + i)
            for i in range(13)
        ]
        pool = [
            Player("dst-1", "DST1", Position.DST, projected_points=125, adp=150.0),
            Player("wr-late", "WR Late", Position.WR, projected_points=50, adp=160.0),
            Player("k-1", "K1", Position.K, projected_points=130, adp=151.0),
        ]
        league = _league()
        penultimate = (league.rounds - 1) * 12 + 1
        state = DraftState(
            team_count=12,
            pick_history=tuple(Pick(p, team_on_clock(p, 12), f"g-{p}") for p in range(1, penultimate)),
            reserved_rosters={"1": tuple(p.id for p in st_roster)},
        )
        limit = 5

    v4_live = recommend_v4(pool, state, league, limit=limit)
    v5_live = recommend_v5(pool, state, _zero_delta_settings(league), limit=limit)
    v4_projected = [_project_result(item) for item in v4_live]
    v5_projected = [_project_result(item) for item in v5_live]

    assert [item["player_id"] for item in v5_projected] == [item["player_id"] for item in v4_projected]
    for v4_item, v5_item in zip(v4_projected, v5_projected, strict=True):
        assert v5_item["dvs_score"] == pytest.approx(v4_item["dvs_score"], abs=1e-4)
        assert v5_item["tier_label"] == v4_item["tier_label"]
        assert v5_item["reasons"] == v4_item["reasons"]
        for key, value in v4_item["breakdown"].items():
            assert key not in V5_ONLY_BREAKDOWN_KEYS
            assert v5_item["breakdown"][key] == pytest.approx(value, abs=1e-4)

    for live_item, expected in zip(v4_projected, v4_results, strict=True):
        assert live_item["player_id"] == expected["player_id"]
        assert live_item["dvs_score"] == pytest.approx(expected["dvs_score"], abs=1e-4)


def test_v5_breakdown_includes_policy_fields():
    pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=55, adp=180.0, tier=5),
        Player("wr-1", "WR1", Position.WR, projected_points=50, adp=181.0, tier=5),
    ]
    roster_ids = tuple(f"p-{index}" for index in range(13))
    roster_players = [
        Player(f"p-{index}", f"P{index}", Position.WR if index % 2 else Position.RB, projected_points=100 - index)
        for index in range(13)
    ]
    pool.extend(roster_players)
    league = LeagueSettings(
        team_count=12,
        roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "BENCH": 6, "K": 1, "DST": 1},
        user_team_id="1",
        formula_params=V5FormulaParams(),
    )
    from dvs_engine import Pick, team_on_clock

    state = DraftState(
        team_count=12,
        pick_history=tuple(Pick(pick, team_on_clock(pick, 12), f"g-{pick}") for pick in range(1, 169)),
        reserved_rosters={"1": roster_ids},
    )
    result = recommend_v5(pool[:2], state, league, limit=2)[0]
    breakdown = as_jsonable(result.breakdown)
    assert "negative_vorp_adjustment" in breakdown
    assert "v5_policy_strength" in breakdown
    assert breakdown["v5_policy_strength"] == 1.0
