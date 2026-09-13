"""Fake OddsProvider for tests and local development without an API key."""

from __future__ import annotations

from draft_api.implied_totals import GameLine


class FakeOddsProvider:
    """Returns a fixed list of game lines supplied at construction."""

    def __init__(self, games: list[GameLine] | None = None) -> None:
        self._games = list(games or [])

    def fetch_nfl_odds(self) -> list[GameLine]:
        return list(self._games)
