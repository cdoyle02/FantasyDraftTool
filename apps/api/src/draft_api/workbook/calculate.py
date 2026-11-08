"""Pure net matchup helpers for Workbook positional grades."""

from __future__ import annotations

from dataclasses import dataclass


def mean_net(off: float | None, opp_def: float | None) -> float | None:
    """Average offensive and opposing defensive net DSR when both are known."""
    if off is None or opp_def is None:
        return None
    return (off + opp_def) / 2.0


def comb_net_dsr(a: float | None, b: float | None) -> float | None:
    """Combine two net DSR values via simple mean (e.g. two teams' rates)."""
    if a is None or b is None:
        return None
    return (a + b) / 2.0


def net_dsr_diff(team_net: float | None, opp_net: float | None) -> float | None:
    """Matchup edge: team combined net minus opponent combined net."""
    if team_net is None or opp_net is None:
        return None
    return round(team_net - opp_net, 9)


@dataclass(frozen=True, slots=True)
class DriveOutcome:
    team: str
    week: int
    success: bool


def drive_success_rate(
    drives: list[DriveOutcome], *, team: str, weeks: set[int]
) -> float | None:
    """Share of drives that gained a first down or touchdown."""
    matched = [d for d in drives if d.team == team and d.week in weeks]
    if not matched:
        return None
    successes = sum(1 for d in matched if d.success)
    return successes / len(matched)


def explosive_pass(yards: float) -> bool:
    """True when a pass gains more than 15 yards."""
    return yards > 15


def explosive_run(yards: float) -> bool:
    """True when a rush gains more than 10 yards."""
    return yards > 10


@dataclass(frozen=True, slots=True)
class PassPlay:
    team: str
    week: int
    is_pass: bool
    xpass: float | None


def pass_rate_over_expectation(
    plays: list[PassPlay], *, team: str, weeks: set[int]
) -> float | None:
    """Mean (actual pass − expected pass) × 100, nflfastR-style percentage points."""
    eligible = [
        p for p in plays if p.team == team and p.week in weeks and p.xpass is not None
    ]
    if not eligible:
        return None
    total = sum((1.0 if p.is_pass else 0.0) - p.xpass for p in eligible)
    return (total / len(eligible)) * 100.0
