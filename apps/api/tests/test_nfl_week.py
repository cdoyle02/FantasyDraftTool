from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from draft_api.nfl_week import (
    fantasy_week_number,
    fantasy_week_window,
    game_in_window,
)

ET = ZoneInfo("America/New_York")
WEEK1_TUESDAY = date(2026, 9, 8)


def test_monday_sept_14_still_week_1():
    # Monday Sep 14 2026 is still Week 1 (new week starts Tuesday).
    now = datetime(2026, 9, 14, 15, 0, tzinfo=ET)
    window = fantasy_week_window(now, season_week1_tuesday=WEEK1_TUESDAY)
    assert window.week == 1
    assert window.start.date() == date(2026, 9, 8)
    assert window.end.date() == date(2026, 9, 14)
    assert window.start.timetz().hour == 0
    assert window.end.time() == time(23, 59, 59, 999999)


def test_tuesday_sept_15_starts_week_2():
    now = datetime(2026, 9, 15, 0, 0, tzinfo=ET)
    window = fantasy_week_window(now, season_week1_tuesday=WEEK1_TUESDAY)
    assert window.week == 2
    assert window.start.date() == date(2026, 9, 15)
    assert window.end.date() == date(2026, 9, 21)


def test_saturday_in_week_1_window():
    now = datetime(2026, 9, 12, 19, 0, tzinfo=ET)
    window = fantasy_week_window(now, season_week1_tuesday=WEEK1_TUESDAY)
    assert window.week == 1
    assert fantasy_week_number(now, season_week1_tuesday=WEEK1_TUESDAY) == 1


def test_game_in_window_filters_by_commence_time():
    now = datetime(2026, 9, 12, 12, 0, tzinfo=ET)
    window = fantasy_week_window(now, season_week1_tuesday=WEEK1_TUESDAY)
    inside = datetime(2026, 9, 14, 20, 0, tzinfo=timezone.utc)
    outside = datetime(2026, 9, 15, 0, 30, tzinfo=ET)
    assert game_in_window(inside, window) is True
    assert game_in_window(outside, window) is False
