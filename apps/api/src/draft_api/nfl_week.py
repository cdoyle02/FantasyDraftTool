"""NFL fantasy week windows: Tuesday 00:00 through Monday 23:59:59.999999."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = ZoneInfo("America/New_York")
# 2026 Week 1 fantasy slate starts Tuesday Sep 8 (Mon Sep 14 still Week 1).
DEFAULT_SEASON_WEEK1_TUESDAY = date(2026, 9, 8)


@dataclass(frozen=True, slots=True)
class FantasyWeekWindow:
    week: int
    start: datetime
    end: datetime
    tz: ZoneInfo


def _parse_season_week1(value: str | None) -> date:
    if not value:
        return DEFAULT_SEASON_WEEK1_TUESDAY
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"NFL_SEASON_WEEK1_TUESDAY must be an ISO date (YYYY-MM-DD), got {value!r}"
        ) from exc


def season_week1_tuesday_from_env() -> date:
    return _parse_season_week1(os.getenv("NFL_SEASON_WEEK1_TUESDAY"))


def _as_local(now: datetime, tz: ZoneInfo) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def _tuesday_start_of_week(local_now: datetime) -> datetime:
    """Return Tuesday 00:00 of the fantasy week containing local_now."""
    local_date = local_now.date()
    # Python weekday: Mon=0 … Sun=6. Tuesday=1.
    days_since_tuesday = (local_date.weekday() - 1) % 7
    tuesday = local_date - timedelta(days=days_since_tuesday)
    return datetime.combine(tuesday, time.min, tzinfo=local_now.tzinfo)


def fantasy_week_window(
    now: datetime,
    *,
    season_week1_tuesday: date | None = None,
    tz: ZoneInfo = DEFAULT_TZ,
) -> FantasyWeekWindow:
    """Tue–Mon window and 1-based week number for the current slate."""
    week1 = season_week1_tuesday or DEFAULT_SEASON_WEEK1_TUESDAY
    local_now = _as_local(now, tz)
    start = _tuesday_start_of_week(local_now)
    end = datetime.combine(
        start.date() + timedelta(days=6),
        time(23, 59, 59, 999999),
        tzinfo=start.tzinfo,
    )
    week = fantasy_week_number(local_now, season_week1_tuesday=week1, tz=tz)
    return FantasyWeekWindow(week=week, start=start, end=end, tz=tz)


def fantasy_week_number(
    now: datetime,
    *,
    season_week1_tuesday: date | None = None,
    tz: ZoneInfo = DEFAULT_TZ,
) -> int:
    week1 = season_week1_tuesday or DEFAULT_SEASON_WEEK1_TUESDAY
    local_now = _as_local(now, tz)
    start = _tuesday_start_of_week(local_now).date()
    delta_days = (start - week1).days
    if delta_days < 0:
        return 1
    return (delta_days // 7) + 1


def game_in_window(commence_time: datetime, window: FantasyWeekWindow) -> bool:
    """True when kickoff falls inside the fantasy week window."""
    local_kick = _as_local(commence_time, window.tz)
    return window.start <= local_kick <= window.end
