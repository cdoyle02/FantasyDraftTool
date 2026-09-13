"""Assemble current-week NFL odds + ranked D/ST plays."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from draft_api.implied_totals import AnnotatedGame, GameLine, annotate_game, rank_dst_plays
from draft_api.nfl_week import FantasyWeekWindow, fantasy_week_window, game_in_window, season_week1_tuesday_from_env
from draft_api.odds.provider import OddsProvider


def filter_games_for_week(games: list[GameLine], window: FantasyWeekWindow) -> list[GameLine]:
    return [game for game in games if game_in_window(game.commence_time, window)]


def annotated_game_to_dict(game: AnnotatedGame) -> dict[str, Any]:
    return {
        "homeTeam": game.home_team,
        "awayTeam": game.away_team,
        "commenceTime": game.commence_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "spread": game.spread,
        "total": game.total,
        "favoriteTeam": game.favorite_team,
        "underdogTeam": game.underdog_team,
        "favoriteImplied": game.favorite_implied,
        "underdogImplied": game.underdog_implied,
        "dstPlayTeam": game.dst_play_team,
        "bookmaker": game.bookmaker,
    }


def build_week_odds_payload(
    provider: OddsProvider,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch odds, filter to current fantasy week, rank by underdog implied."""
    moment = now or datetime.now(timezone.utc)
    window = fantasy_week_window(moment, season_week1_tuesday=season_week1_tuesday_from_env())
    lines = filter_games_for_week(provider.fetch_nfl_odds(), window)
    ranked = rank_dst_plays([annotate_game(line) for line in lines])
    return {
        "week": window.week,
        "windowStart": window.start.isoformat(),
        "windowEnd": window.end.isoformat(),
        "fetchedAt": moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "games": [annotated_game_to_dict(game) for game in ranked],
    }
