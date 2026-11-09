"""Offline Tier 1 backtest regression lock."""

import json
from pathlib import Path

from draft_api.sos.backtest import run_tier1_backtest, spearman_rho

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINI = FIXTURES / "tier1_backtest_mini.json"
SUMMARY = FIXTURES / "tier1_backtest_summary.json"


def test_spearman_identity():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert spearman_rho(xs, xs) == 1.0


def test_backtest_matches_committed_summary():
    expected = json.loads(SUMMARY.read_text(encoding="utf-8"))
    actual = run_tier1_backtest(MINI)
    for key in ("n_observations", "n_weeks", "spearman_rho", "baseline_rho"):
        assert actual[key] == expected[key]
