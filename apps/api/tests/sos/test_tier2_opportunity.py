"""Tier 2 opportunity: EPA softness × snap usage × game script."""

from datetime import datetime, timezone

from draft_api.implied_totals import GameLine
from draft_api.sos.calculate import CompletedGame
from draft_api.sos.tier2 import build_tier2_player_opportunity
from draft_api.sos.tier2_epa import build_defense_epa_softness_index
from draft_api.sos.tier2_snap import build_snap_pct_index
from draft_api.sos.usage import build_usage_index


def _pts(rb: float) -> dict:
    return {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0, "DST": 0.0}


GAMES = [
    CompletedGame(week=1, offense="AAA", defense="BBB", points=_pts(10)),
    CompletedGame(week=2, offense="AAA", defense="BBB", points=_pts(10)),
]

SCHEDULE = {"AAA": {3: "BBB"}}

STATS = [
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "opponent_team": "BBB",
        "player_id": "R1",
        "player_display_name": "Workhorse",
        "carries": "20",
        "rushing_epa": "5",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "opponent_team": "BBB",
        "player_id": "R1",
        "player_display_name": "Workhorse",
        "carries": "20",
        "rushing_epa": "5",
    },
]

SNAP = [
    {
        "season": "2026",
        "week": "1",
        "game_type": "REG",
        "team": "AAA",
        "player": "Workhorse",
        "offense_pct": "0.80",
    },
    {
        "season": "2026",
        "week": "2",
        "game_type": "REG",
        "team": "AAA",
        "player": "Workhorse",
        "offense_pct": "0.80",
    },
]


def test_tier2_opportunity_includes_game_script_boost():
    _, rating_weeks, softness = build_defense_epa_softness_index(
        position="RB",
        window="season",
        games=GAMES,
        stats_rows=STATS,
        teams=["BBB"],
        season=2026,
    )
    snap_index = build_snap_pct_index(SNAP, season=2026)
    usage = build_usage_index(
        STATS,
        position="RB",
        weeks=set(rating_weeks),
        season=2026,
        snap_pct_index=snap_index,
    )
    game = GameLine(
        home_team="AAA",
        away_team="BBB",
        commence_time=datetime(2026, 11, 8, tzinfo=timezone.utc),
        spread=-3.0,
        total=52.0,
        favorite_team="AAA",
        underdog_team="BBB",
        bookmaker="test",
    )
    rows = build_tier2_player_opportunity(
        position="RB",
        usage_index=usage,
        defense_softness=softness,
        schedule={"AAA": {**{w: None for w in range(1, 19)}, 3: "BBB"}},
        week=3,
        game_lines=[game],
        snap_filtered=True,
    )
    row = rows[0]
    assert row["opportunity"] is not None
    assert row["adjustedSoftness"] is not None
    assert row["softnessScore"] is not None
    assert row["gameScriptDelta"] is not None
    assert row["gameScriptDelta"] > 0
