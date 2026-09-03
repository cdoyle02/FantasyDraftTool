"""Canonical Formula V4 full-output golden regression."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dvs_engine import FormulaParams, LeagueSettings, as_jsonable, recommend_v4

from v4_golden_helpers import (
    FIXTURES_DIR,
    V5_ONLY_BREAKDOWN_KEYS,
    V5_ONLY_PARAM_KEYS,
    assert_no_v5_keys,
    build_golden_states,
    browser_payload,
    canonical_json,
)

GOLDEN_NAMES = (
    "early_round",
    "mid_round",
    "starters_nearly_complete",
    "late_round",
    "own_handcuff",
    "special_teams_window",
)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _recommendations_match(live: list[dict], expected: list[dict]) -> None:
    assert len(live) == len(expected)
    for live_item, expected_item in zip(live, expected, strict=True):
        assert live_item["player_id"] == expected_item["player_id"]
        assert live_item["dvs_score"] == pytest.approx(expected_item["dvs_score"], abs=1e-4)
        assert live_item["tier_label"] == expected_item["tier_label"]
        assert live_item["reasons"] == expected_item["reasons"]
        live_breakdown = live_item["breakdown"]
        expected_breakdown = expected_item["breakdown"]
        for key, value in expected_breakdown.items():
            assert key not in V5_ONLY_BREAKDOWN_KEYS
            assert live_breakdown[key] == pytest.approx(value, abs=1e-4)


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_v4_golden_matches_committed_fixture(name: str):
    fixture = _load_fixture(name)
    live = build_golden_states()[name]
    assert live["name"] == fixture["name"]
    assert live["count"] == fixture["count"]
    assert live["configuration"]["formulaVersion"] == 4
    assert live["configuration"]["simulationSeed"] == fixture["configuration"]["simulationSeed"]
    assert_no_v5_keys(live["configuration"]["formulaParams"])
    _recommendations_match(live["recommendations"], fixture["recommendations"])


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_recommend_dispatch_equals_recommend_v4(name: str):
    fixture = _load_fixture(name)
    live = build_golden_states()[name]
    assert canonical_json(live["recommendations"]) == canonical_json(fixture["recommendations"])


def test_browser_early_golden_matches_fixture():
    fixture = _load_fixture("browser_early")
    from dvs_engine import DraftState, Player, Position

    live = browser_payload(
        [
            Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
            Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
        ],
        DraftState(team_count=2),
        LeagueSettings(
            team_count=2,
            roster_slots={"QB": 0, "RB": 1, "WR": 1, "TE": 0, "FLEX": 0, "BENCH": 0, "K": 0, "DST": 0},
            user_team_id="1",
            formula_params=FormulaParams(),
        ),
        limit=2,
    )
    assert live["configuration"]["formulaVersion"] == 4
    assert_no_v5_keys(live)
    assert canonical_json(live["recommendations"]) == canonical_json(fixture["recommendations"])


def test_v4_payloads_exclude_v5_only_keys():
    for name in GOLDEN_NAMES:
        fixture = _load_fixture(name)
        assert_no_v5_keys(fixture)
        for key in V5_ONLY_PARAM_KEYS:
            assert key not in fixture["configuration"]["formulaParams"]


def test_v4_roster_helpers_have_no_v5_branches():
    import inspect

    from dvs_engine import formula, v4

    for name in ("roster_shape_need", "guardrail_adjustment", "depth_target"):
        source = inspect.getsource(getattr(formula, name))
        assert "formula_version == 5" not in source
        assert "V5FormulaParams" not in source
        assert "v5_policy" not in source

    shape_source = inspect.getsource(v4.shape_adjustment)
    assert "formula_version == 5" not in shape_source
    assert "V5FormulaParams" not in shape_source
    assert "v5_policy" not in shape_source

    v4_source = inspect.getsource(v4)
    assert "from .v5" not in v4_source
    assert "import v5" not in v4_source
