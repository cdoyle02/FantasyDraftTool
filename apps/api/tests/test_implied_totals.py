from datetime import datetime, timezone

from draft_api.implied_totals import (
    GameLine,
    annotate_game,
    implied_team_totals,
    rank_dst_plays,
)


def test_implied_team_totals_favorite_and_underdog():
    # O/U 41.5, favorite by 9.5 → fav 25.5, dog 16.0
    favorite, underdog = implied_team_totals(total=41.5, spread=-9.5)
    assert favorite == 25.5
    assert underdog == 16.0


def test_implied_team_totals_uses_absolute_spread():
    favorite, underdog = implied_team_totals(total=44.0, spread=6.0)
    assert favorite == 25.0
    assert underdog == 19.0


def test_annotate_game_sets_favorite_dst_play():
    game = annotate_game(
        GameLine(
            home_team="KC",
            away_team="LV",
            commence_time=datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc),
            spread=-9.5,
            total=41.5,
            favorite_team="KC",
            underdog_team="LV",
            bookmaker="consensus",
        )
    )
    assert game.favorite_implied == 25.5
    assert game.underdog_implied == 16.0
    assert game.dst_play_team == "KC"


def test_rank_dst_plays_sorts_by_lowest_underdog_implied():
    low = annotate_game(
        GameLine(
            home_team="KC",
            away_team="LV",
            commence_time=datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc),
            spread=-9.5,
            total=41.5,
            favorite_team="KC",
            underdog_team="LV",
            bookmaker="consensus",
        )
    )
    high = annotate_game(
        GameLine(
            home_team="BUF",
            away_team="MIA",
            commence_time=datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc),
            spread=-3.0,
            total=48.0,
            favorite_team="BUF",
            underdog_team="MIA",
            bookmaker="consensus",
        )
    )
    ranked = rank_dst_plays([high, low])
    assert [g.dst_play_team for g in ranked] == ["KC", "BUF"]
    assert ranked[0].underdog_implied < ranked[1].underdog_implied
