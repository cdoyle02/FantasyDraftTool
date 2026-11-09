"""ESPN-style D/ST fantasy points from nflverse team-week defensive stats.

Used for strength-of-schedule only (not live waiver ranks). Scoring mirrors
common ESPN defaults:
  sack 1 · INT 2 · FR 2 · TD 6 · safety 2 · blocked kick 2
  plus points-allowed brackets (0→10 … 35+→-5).
"""

from __future__ import annotations


def points_allowed_fantasy(points_allowed: float) -> float:
    """ESPN points-allowed bracket for a D/ST."""
    pts = int(points_allowed)
    if pts <= 0:
        return 10.0
    if pts <= 6:
        return 7.0
    if pts <= 13:
        return 4.0
    if pts <= 17:
        return 1.0
    if pts <= 21:
        return 0.0
    if pts <= 27:
        return -1.0
    if pts <= 34:
        return -4.0
    return -5.0


def dst_fantasy_points(
    *,
    sacks: float = 0.0,
    interceptions: float = 0.0,
    fumble_recoveries: float = 0.0,
    defensive_tds: float = 0.0,
    special_teams_tds: float = 0.0,
    safeties: float = 0.0,
    blocked_kicks: float = 0.0,
    points_allowed: float = 0.0,
) -> float:
    """Compute one-game D/ST fantasy total."""
    return (
        1.0 * sacks
        + 2.0 * interceptions
        + 2.0 * fumble_recoveries
        + 6.0 * (defensive_tds + special_teams_tds)
        + 2.0 * safeties
        + 2.0 * blocked_kicks
        + points_allowed_fantasy(points_allowed)
    )
