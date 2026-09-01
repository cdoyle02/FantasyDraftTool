"""One-turn lookahead and corrected wait-loss for the V4 decision engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .lineup import marginal_value
from .models import FormulaParams, LeagueSettings, Player, Position


def expected_fallback_value(
    player: Player,
    available: Sequence[Player],
    marginals: Mapping[str, float],
    survival_by_id: Mapping[str, float],
) -> float:
    """Expected best same-position marginal value available at the next turn."""
    ranked = [
        candidate
        for candidate in available
        if candidate.position == player.position and candidate.id != player.id
    ]
    ranked.sort(key=lambda candidate: marginals.get(candidate.id, 0.0), reverse=True)
    fallback = 0.0
    survival_product = 1.0
    for candidate in ranked:
        survival = survival_by_id.get(candidate.id, 0.5)
        fallback += marginals.get(candidate.id, 0.0) * survival * survival_product
        survival_product *= 1.0 - survival
    return fallback


def wait_value(
    player: Player,
    marginal: float,
    fallback: float,
    survival: float,
) -> float:
    """Expected value of waiting on this player until the next pick."""
    return survival * marginal + (1.0 - survival) * fallback


def wait_loss_v4(
    marginal: float,
    fallback: float,
    survival: float,
) -> float:
    """Corrected wait-loss: (1 - survival) * max(0, marginal - fallback)."""
    return (1.0 - survival) * max(0.0, marginal - fallback)


def expected_best_surviving(
    pool: Sequence[Player],
    marginals: Mapping[str, float],
    survival_by_id: Mapping[str, float],
    exclude_ids: frozenset[str] | None = None,
) -> float:
    """Expected max marginal among surviving players in the pool."""
    excluded = exclude_ids or frozenset()
    ranked = [
        player
        for player in pool
        if player.id not in excluded and marginals.get(player.id, 0.0) > 0.0
    ]
    ranked.sort(key=lambda player: marginals.get(player.id, 0.0), reverse=True)
    expected = 0.0
    survival_product = 1.0
    for player in ranked:
        survival = survival_by_id.get(player.id, 0.5)
        expected += marginals.get(player.id, 0.0) * survival * survival_product
        survival_product *= 1.0 - survival
    return expected


def select_candidates(
    available: Sequence[Player],
    marginals: Mapping[str, float],
    wait_losses: Mapping[str, float],
    params: FormulaParams,
) -> list[Player]:
    """Top prescore candidates plus the best player at each position."""
    limit = max(1, params.lookahead_candidates)
    prescore = {
        player.id: marginals.get(player.id, 0.0) + 0.5 * wait_losses.get(player.id, 0.0)
        for player in available
    }
    ranked = sorted(
        available,
        key=lambda player: (-prescore[player.id], player.adp or float("inf"), player.id),
    )
    chosen: dict[str, Player] = {}
    for player in ranked[:limit]:
        chosen[player.id] = player
    for position in (
        Position.QB,
        Position.RB,
        Position.WR,
        Position.TE,
        Position.K,
        Position.DST,
    ):
        position_players = [player for player in available if player.position == position]
        if not position_players:
            continue
        best = max(
            position_players,
            key=lambda player: (
                marginals.get(player.id, 0.0),
                -prescore.get(player.id, 0.0),
            ),
        )
        chosen[best.id] = best
    return sorted(
        chosen.values(),
        key=lambda player: (-prescore[player.id], player.adp or float("inf"), player.id),
    )


def build_lookahead_pool(
    available: Sequence[Player],
    marginals: Mapping[str, float],
    params: FormulaParams,
) -> list[Player]:
    """Top players per position for next-turn expectation."""
    per_position = max(1, params.lookahead_pool_per_position)
    pool: dict[str, Player] = {}
    for position in (
        Position.QB,
        Position.RB,
        Position.WR,
        Position.TE,
        Position.K,
        Position.DST,
    ):
        ranked = sorted(
            [player for player in available if player.position == position],
            key=lambda player: marginals.get(player.id, 0.0),
            reverse=True,
        )
        for player in ranked[:per_position]:
            pool[player.id] = player
    return list(pool.values())


class MarginalCache:
    """Memoize marginal_value calls keyed by roster composition."""

    def __init__(
        self,
        settings: LeagueSettings,
        levels: Mapping[Position, float],
        params: FormulaParams,
        caps: Mapping[Position, int] | None,
    ) -> None:
        self._settings = settings
        self._levels = levels
        self._params = params
        self._caps = caps
        self._cache: dict[tuple[tuple[str, ...], str], float] = {}

    def marginal(self, player: Player, roster: Sequence[Player]) -> float:
        roster_key = tuple(sorted(item.id for item in roster))
        cache_key = (roster_key, player.id)
        if cache_key not in self._cache:
            self._cache[cache_key] = marginal_value(
                player, roster, self._settings, self._levels, self._params, self._caps
            )
        return self._cache[cache_key]


def next_pick_value(
    drafted_player: Player,
    roster: Sequence[Player],
    pool: Sequence[Player],
    cache: MarginalCache,
    survival_by_id: Mapping[str, float],
) -> float:
    """Expected best marginal at the next pick after drafting this player."""
    simulated = (*roster, drafted_player)
    marginals = {player.id: cache.marginal(player, simulated) for player in pool}
    return expected_best_surviving(
        pool,
        marginals,
        survival_by_id,
        exclude_ids=frozenset({drafted_player.id}),
    )
