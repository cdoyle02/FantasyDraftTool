"""Pure net matchup helpers for Workbook positional grades."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

StatWeekMode = Literal["l4", "season", "custom"]
RateSide = Literal["off", "def"]


def resolve_stat_weeks(
    *,
    mode: StatWeekMode,
    rated_through_week: int,
    custom_start: int | None,
    custom_end: int | None,
) -> set[int]:
    """Resolve the completed-stat window used by Workbook Net rows."""
    if rated_through_week < 1:
        return set()

    if mode == "l4":
        start = max(1, rated_through_week - 3)
        return set(range(start, rated_through_week + 1))

    if mode == "season":
        return set(range(1, rated_through_week + 1))

    if mode == "custom":
        start = max(1, custom_start if custom_start is not None else 1)
        end = min(18, custom_end if custom_end is not None else rated_through_week)
        if start > end:
            return set()
        return set(range(start, end + 1))

    raise ValueError(f"Unsupported stat week mode: {mode}")


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
class TeamRateSlice:
    """One team/week OFF or DEF rate bag for Workbook environment metrics."""

    team: str
    week: int
    side: RateSide
    proe: float | None = None
    pass_plays: float | None = None
    epa_pass: float | None = None
    xplsv_pass: float | None = None
    run_plays: float | None = None
    epa_run: float | None = None
    xplsv_run: float | None = None


@dataclass(frozen=True, slots=True)
class TeamEnvRates:
    """Averaged team OFF or DEF rates used to build one matchup Net row."""

    proe: float | None = None
    pass_plays: float | None = None
    epa_pass: float | None = None
    xplsv_pass: float | None = None
    run_plays: float | None = None
    epa_run: float | None = None
    xplsv_run: float | None = None


def _mean_present(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def build_team_env_rates(
    slices: Sequence[TeamRateSlice],
    *,
    team: str,
    side: RateSide,
    weeks: set[int],
) -> TeamEnvRates:
    """Average matching team/week rate slices into one OFF or DEF rate bag."""
    matched = [
        rate_slice
        for rate_slice in slices
        if rate_slice.team == team and rate_slice.side == side and rate_slice.week in weeks
    ]
    return TeamEnvRates(
        proe=_mean_present([rate_slice.proe for rate_slice in matched]),
        pass_plays=_mean_present([rate_slice.pass_plays for rate_slice in matched]),
        epa_pass=_mean_present([rate_slice.epa_pass for rate_slice in matched]),
        xplsv_pass=_mean_present([rate_slice.xplsv_pass for rate_slice in matched]),
        run_plays=_mean_present([rate_slice.run_plays for rate_slice in matched]),
        epa_run=_mean_present([rate_slice.epa_run for rate_slice in matched]),
        xplsv_run=_mean_present([rate_slice.xplsv_run for rate_slice in matched]),
    )


def build_game_environment_net(
    *,
    team_off: TeamEnvRates,
    opp_def: TeamEnvRates,
    team_net_dsr: float | None,
    opp_net_dsr: float | None,
    implied_points: float | None,
) -> dict[str, float | None]:
    """Build the camelCase game-environment Net row consumed by the API later."""
    return {
        "netDsr": team_net_dsr,
        "combNetDsr": comb_net_dsr(team_net_dsr, opp_net_dsr),
        "netDsrDiff": net_dsr_diff(team_net_dsr, opp_net_dsr),
        "netProe": mean_net(team_off.proe, opp_def.proe),
        "netPassPlays": mean_net(team_off.pass_plays, opp_def.pass_plays),
        "netEpaPass": mean_net(team_off.epa_pass, opp_def.epa_pass),
        "netXplsvPass": mean_net(team_off.xplsv_pass, opp_def.xplsv_pass),
        "netRunPlays": mean_net(team_off.run_plays, opp_def.run_plays),
        "netEpaRun": mean_net(team_off.epa_run, opp_def.epa_run),
        "netXplsvRun": mean_net(team_off.xplsv_run, opp_def.xplsv_run),
        "vegasImpliedPoints": implied_points,
    }


def build_positional_net(
    off: Mapping[str, float | None], opp_def: Mapping[str, float | None]
) -> dict[str, float | None]:
    """Average each positional OFF metric with its matching opponent DEF metric."""
    return {key: mean_net(off.get(key), opp_def.get(key)) for key in off.keys() | opp_def.keys()}


def is_main_slate(weekday_local: int, kickoff_hour_local: int) -> bool:
    """Return True for Sunday early/late kickoffs before 7pm America/Chicago."""
    return weekday_local == 6 and kickoff_hour_local < 19


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
    total = 0.0
    eligible_count = 0
    for play in plays:
        if play.team != team or play.week not in weeks or play.xpass is None:
            continue
        total += (1.0 if play.is_pass else 0.0) - play.xpass
        eligible_count += 1
    if eligible_count == 0:
        return None
    return (total / eligible_count) * 100.0
