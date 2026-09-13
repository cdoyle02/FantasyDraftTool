"""Implied team totals and D/ST ranking from Vegas spread + total."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class GameLine:
    """Provider-agnostic game odds before implied totals are applied."""

    home_team: str
    away_team: str
    commence_time: datetime
    spread: float
    total: float
    favorite_team: str
    underdog_team: str
    bookmaker: str


@dataclass(frozen=True, slots=True)
class AnnotatedGame(GameLine):
    """Game odds plus implied points and the D/ST stream candidate."""

    favorite_implied: float
    underdog_implied: float
    dst_play_team: str


def implied_team_totals(*, total: float, spread: float) -> tuple[float, float]:
    """Return (favorite_implied, underdog_implied) from O/U and spread.

    Spread may be signed either way; magnitude is what matters:
    favorite = total/2 + |spread|/2, underdog = total/2 - |spread|/2.
    """
    spread_mag = abs(spread)
    half_total = total / 2.0
    half_spread = spread_mag / 2.0
    return half_total + half_spread, half_total - half_spread


def annotate_game(game: GameLine) -> AnnotatedGame:
    """Attach implied totals; D/ST play is always the favorite."""
    favorite_implied, underdog_implied = implied_team_totals(
        total=game.total, spread=game.spread
    )
    return AnnotatedGame(
        home_team=game.home_team,
        away_team=game.away_team,
        commence_time=game.commence_time,
        spread=game.spread,
        total=game.total,
        favorite_team=game.favorite_team,
        underdog_team=game.underdog_team,
        bookmaker=game.bookmaker,
        favorite_implied=favorite_implied,
        underdog_implied=underdog_implied,
        dst_play_team=game.favorite_team,
    )


def rank_dst_plays(games: list[AnnotatedGame] | list[GameLine]) -> list[AnnotatedGame]:
    """Rank favorite D/STs by lowest underdog implied points allowed."""
    annotated = [
        game if isinstance(game, AnnotatedGame) else annotate_game(game)
        for game in games
    ]
    return sorted(annotated, key=lambda g: (g.underdog_implied, g.commence_time.isoformat()))
