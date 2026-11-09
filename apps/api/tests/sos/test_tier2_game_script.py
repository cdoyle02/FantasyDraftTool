"""Game-script softness adjustment from implied totals."""

from draft_api.sos.tier2_game_script import (
    GAME_SCRIPT_CENTER,
    adjust_softness_score,
    implied_points_for_team,
)
from draft_api.implied_totals import GameLine
from datetime import datetime, timezone


def _line(*, home: str, away: str, spread: float, total: float) -> GameLine:
    fav = home if spread < 0 else away
    dog = away if spread < 0 else home
    return GameLine(
        home_team=home,
        away_team=away,
        commence_time=datetime(2026, 11, 8, tzinfo=timezone.utc),
        spread=spread,
        total=total,
        favorite_team=fav,
        underdog_team=dog,
        bookmaker="test",
    )


def test_high_implied_softens_matchup():
    adjusted, delta, applied = adjust_softness_score(
        softness_score=0.5,
        team_implied=30.0,
        center=GAME_SCRIPT_CENTER,
    )
    assert applied is True
    assert delta > 0
    assert adjusted > 0.5


def test_low_implied_tightens_matchup():
    adjusted, delta, applied = adjust_softness_score(
        softness_score=0.5,
        team_implied=16.0,
        center=GAME_SCRIPT_CENTER,
    )
    assert applied is True
    assert delta < 0
    assert adjusted < 0.5


def test_null_implied_leaves_score_unchanged():
    adjusted, delta, applied = adjust_softness_score(softness_score=0.5, team_implied=None)
    assert applied is False
    assert delta == 0.0
    assert adjusted == 0.5


def test_implied_points_for_home_favorite():
    game = _line(home="KC", away="DEN", spread=-3.0, total=48.0)
    kc = implied_points_for_team(game, team="KC")
    den = implied_points_for_team(game, team="DEN")
    assert kc is not None and den is not None
    assert kc > den
