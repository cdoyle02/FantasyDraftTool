"""Fantasy Footballers tier signals for the V4 decision engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import FormulaParams, Player


def tier_cliff(player: Player, available: Sequence[Player]) -> float:
    """Projected-point drop from the player's tier floor to the next tier ceiling."""
    same_position = [candidate for candidate in available if candidate.position == player.position]
    current_tier = [
        candidate.projected_points
        for candidate in same_position
        if candidate.tier == player.tier
    ]
    if not current_tier:
        return 0.0
    current_floor = min(current_tier)
    next_tier = player.tier + 1
    while next_tier <= max((candidate.tier for candidate in same_position), default=player.tier):
        lower_tier_points = [
            candidate.projected_points
            for candidate in same_position
            if candidate.tier == next_tier
        ]
        if lower_tier_points:
            return max(0.0, current_floor - max(lower_tier_points))
        next_tier += 1
    return 0.0


def players_remaining_in_tier(player: Player, available: Sequence[Player]) -> int:
    return sum(
        1
        for candidate in available
        if candidate.position == player.position and candidate.tier == player.tier
    )


def tier_exhaustion_probability(
    player: Player,
    available: Sequence[Player],
    survival_by_id: Mapping[str, float],
    intervening_picks: int | None = None,
    sim_exhaustion: float | None = None,
) -> float:
    """Probability every player in the tier is gone by the user's next pick."""
    if sim_exhaustion is not None:
        return sim_exhaustion
    tier_members = [
        candidate
        for candidate in available
        if candidate.position == player.position and candidate.tier == player.tier
    ]
    if not tier_members:
        return 0.0
    if intervening_picks is not None and len(tier_members) > intervening_picks:
        return 0.0
    probability = 1.0
    for member in tier_members:
        survival = survival_by_id.get(member.id, 0.5)
        probability *= 1.0 - survival
    return probability


def tier_opportunity_cost(
    player: Player,
    available: Sequence[Player],
    survival_by_id: Mapping[str, float],
    params: FormulaParams,
    intervening_picks: int | None = None,
    sim_exhaustion: float | None = None,
) -> float:
    """Saturating tier cliff weighted by tier exhaustion probability."""
    cliff = tier_cliff(player, available)
    if cliff <= 0.0:
        return 0.0
    scale = params.tier_cliff_scale
    cliff_shrunk = cliff * scale / (cliff + scale)
    exhaustion = tier_exhaustion_probability(
        player,
        available,
        survival_by_id,
        intervening_picks=intervening_picks,
        sim_exhaustion=sim_exhaustion,
    )
    return cliff_shrunk * exhaustion
