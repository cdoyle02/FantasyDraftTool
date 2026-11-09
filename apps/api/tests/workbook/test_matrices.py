"""Tertile matrix tier boundaries."""

from __future__ import annotations

from draft_api.workbook.matrices import Tertile, assign_tertile


def test_assign_tertile_nine_teams_three_each() -> None:
    values = {f"T{i}": float(i) for i in range(1, 10)}
    tiers = assign_tertile(values, higher_is_better=True)
    tops = [team for team, tier in tiers.items() if tier == "top"]
    mids = [team for team, tier in tiers.items() if tier == "mid"]
    bottoms = [team for team, tier in tiers.items() if tier == "bottom"]
    assert len(tops) == 3
    assert len(mids) == 3
    assert len(bottoms) == 3
    assert set(tops) == {"T7", "T8", "T9"}


def test_assign_tertile_omits_null_from_rank_pool() -> None:
    values: dict[str, float | None] = {"A": 1.0, "B": None, "C": 3.0, "D": 2.0}
    tiers = assign_tertile(values, higher_is_better=True)
    assert tiers["B"] is None
    assert tiers["C"] == "top"
    assert tiers["A"] == "bottom"


def test_assign_tertile_thirty_two_teams() -> None:
    values = {f"T{i:02d}": float(i) for i in range(1, 33)}
    tiers: dict[str, Tertile | None] = assign_tertile(values, higher_is_better=True)
    assert sum(1 for tier in tiers.values() if tier == "top") == 11
    assert sum(1 for tier in tiers.values() if tier == "mid") == 11
    assert sum(1 for tier in tiers.values() if tier == "bottom") == 10
