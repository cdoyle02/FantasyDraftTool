"""Odds provider IoC: protocol for NFL game lines."""

from __future__ import annotations

from typing import Protocol

from draft_api.implied_totals import GameLine


class OddsProvider(Protocol):
    """Fetch upcoming NFL games with spread + total.

    Implementations may call an external API; callers should treat this as I/O.
    """

    def fetch_nfl_odds(self) -> list[GameLine]:
        """Return provider-normalized game lines (any commence time)."""
        ...
