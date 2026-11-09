"""Tier 1 opportunity = softness × usage share."""

from draft_api.sos.calculate import CompletedGame
from draft_api.sos.tier1 import (
    DefenseSoftness,
    build_defense_softness_index,
    build_player_opportunity,
)
from draft_api.sos.usage import PlayerUsage, build_usage_index


def _pts(rb: float) -> dict:
    return {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0, "DST": 0.0}


GAMES = [
    CompletedGame(week=1, offense="AAA", defense="BBB", points=_pts(22)),
    CompletedGame(week=1, offense="BBB", defense="AAA", points=_pts(8)),
    CompletedGame(week=1, offense="CCC", defense="DDD", points=_pts(10)),
    CompletedGame(week=1, offense="DDD", defense="CCC", points=_pts(12)),
    CompletedGame(week=2, offense="AAA", defense="CCC", points=_pts(18)),
    CompletedGame(week=2, offense="CCC", defense="AAA", points=_pts(14)),
]

SCHEDULE = {
    "AAA": {**{w: None for w in range(1, 19)}, 1: "BBB", 2: "CCC", 3: "DDD"},
    "BBB": {**{w: None for w in range(1, 19)}, 1: "AAA", 2: "DDD", 3: "CCC"},
    "CCC": {**{w: None for w in range(1, 19)}, 1: "DDD", 2: "AAA", 3: "BBB"},
    "DDD": {**{w: None for w in range(1, 19)}, 1: "CCC", 2: "BBB", 3: "AAA"},
}

STATS = [
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RBH",
        "player_display_name": "High Use",
        "carries": "15",
    },
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RBL",
        "player_display_name": "Low Use",
        "carries": "5",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RBH",
        "player_display_name": "High Use",
        "carries": "15",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RBL",
        "player_display_name": "Low Use",
        "carries": "5",
    },
]


def test_soft_matchup_high_usage_beats_tough_low_usage():
    _, rating_weeks, softness = build_defense_softness_index(
        position="RB",
        window="season",
        games=GAMES,
        teams=["AAA", "BBB", "CCC", "DDD"],
    )
    usage = build_usage_index(STATS, position="RB", weeks=set(rating_weeks), season=2026)
    # Week 3: AAA faces DDD (allowing profile from weeks 1-2)
    rows = build_player_opportunity(
        usage_index=usage,
        defense_softness=softness,
        schedule=SCHEDULE,
        week=3,
    )
    high = next(r for r in rows if r["name"] == "High Use")
    low = next(r for r in rows if r["name"] == "Low Use")
    assert high["opponent"] == "DDD"
    assert high["opportunity"] is not None and high["opportunity"] > 0
    assert low["opportunity"] is not None
    assert high["opportunity"] > low["opportunity"]


def test_opportunity_sorts_descending():
    _, rating_weeks, softness = build_defense_softness_index(
        position="RB",
        window="season",
        games=GAMES,
        teams=["AAA", "BBB", "CCC", "DDD"],
    )
    usage = build_usage_index(STATS, position="RB", weeks=set(rating_weeks), season=2026)
    rows = build_player_opportunity(
        usage_index=usage,
        defense_softness=softness,
        schedule=SCHEDULE,
        week=3,
    )
    opportunities = [r["opportunity"] for r in rows if r["opportunity"] is not None]
    assert opportunities == sorted(opportunities, reverse=True)


def test_manual_softness_times_share():
    usage = [
        PlayerUsage(
            gsis_id="X",
            player_name="Test",
            team="AAA",
            position="RB",
            usage_share=0.75,
        )
    ]
    softness = {
        "DDD": DefenseSoftness(defense="DDD", rank=1, softness="soft", softness_score=1.0)
    }
    rows = build_player_opportunity(
        usage_index=usage,
        defense_softness=softness,
        schedule=SCHEDULE,
        week=3,
    )
    assert rows[0]["opportunity"] == 0.75
