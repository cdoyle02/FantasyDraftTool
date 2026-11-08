"""Workbook positional fantasy point formulas (PPR variants)."""

from __future__ import annotations

from typing import Literal

Scoring = Literal["ppr", "half_ppr"]


def receiving_points(
    *,
    receptions: float,
    yards: float,
    tds: float,
    scoring: Scoring,
) -> float:
    """Standard receiving: 0.1/yd, 6/TD, plus full or half PPR."""
    rec_pts = receptions if scoring == "ppr" else receptions * 0.5
    return rec_pts + 0.1 * yards + 6.0 * tds


def rushing_points(*, yards: float, tds: float) -> float:
    """Standard rushing: 0.1/yd, 6/TD."""
    return 0.1 * yards + 6.0 * tds


def passing_points(*, yards: float, tds: float, ints: float = 0) -> float:
    """Standard passing: 0.04/yd, 4/TD, −2/INT."""
    return 0.04 * yards + 4.0 * tds - 2.0 * ints
