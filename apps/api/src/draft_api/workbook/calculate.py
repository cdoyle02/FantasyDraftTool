"""Pure net matchup helpers for Workbook positional grades."""

from __future__ import annotations


def mean_net(off: float | None, opp_def: float | None) -> float | None:
    """Average offensive and opposing defensive net DSR when both are known."""
    if off is None or opp_def is None:
        return None
    return (off + opp_def) / 2.0


def comb_net_dsr(a: float | None, b: float | None) -> float | None:
    """Combine two net DSR components (e.g. pass + rush) via simple mean."""
    if a is None or b is None:
        return None
    return (a + b) / 2.0


def net_dsr_diff(team_net: float | None, opp_net: float | None) -> float | None:
    """Matchup edge: team combined net minus opponent combined net."""
    if team_net is None or opp_net is None:
        return None
    return round(team_net - opp_net, 9)
