"""Deterministic, side-effect-free Draft Value Score calculations."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace
from typing import Iterable, Mapping, Sequence

from .draft import validate_state
from .models import (
    DraftState,
    LeagueSettings,
    Player,
    Position,
    RecommendationBreakdown,
    RecommendationLabel,
    RecommendationResult,
    UserAdjustment,
    team_on_clock,
)

FLEX_POSITIONS = (Position.RB, Position.WR, Position.TE)
SUPERFLEX_POSITIONS = (Position.QB, Position.RB, Position.WR, Position.TE)


def effective_player(player: Player, adjustment: UserAdjustment | None) -> Player:
    """Return a scoring view without mutating imported baseline data."""
    if adjustment is None:
        return player
    return replace(
        player,
        projected_points=player.projected_points + adjustment.points_delta,
        tier=adjustment.tier_override or player.tier,
    )


def replacement_counts(settings: LeagueSettings) -> dict[Position, int]:
    slots = settings.roster_slots
    counts = {
        position: settings.team_count * int(slots.get(position.value, 0))
        for position in (
            Position.QB,
            Position.RB,
            Position.WR,
            Position.TE,
            Position.K,
            Position.DST,
        )
    }
    flex = settings.team_count * int(slots.get("FLEX", 0))
    flex_weights = {Position.RB: 0.45, Position.WR: 0.45, Position.TE: 0.10}
    for position, weight in flex_weights.items():
        counts[position] += round(flex * weight)
    superflex = settings.team_count * int(slots.get("SUPERFLEX", slots.get("SF", 0)))
    superflex_weights = {
        Position.QB: 0.65,
        Position.RB: 0.15,
        Position.WR: 0.15,
        Position.TE: 0.05,
    }
    for position, weight in superflex_weights.items():
        counts[position] += round(superflex * weight)
    return {position: max(1, count) for position, count in counts.items()}


def replacement_levels(
    players: Iterable[Player], settings: LeagueSettings
) -> dict[Position, float]:
    counts = replacement_counts(settings)
    grouped: dict[Position, list[float]] = {position: [] for position in counts}
    for player in players:
        if player.position in grouped:
            grouped[player.position].append(player.projected_points)
    levels: dict[Position, float] = {}
    for position, points in grouped.items():
        ordered = sorted(points, reverse=True)
        index = min(counts[position], len(ordered)) - 1
        levels[position] = ordered[index] if ordered else 0.0
    return levels


def vorp(player: Player, levels: Mapping[Position, float]) -> float:
    return player.projected_points - levels.get(player.position, 0.0)


def tier_cliff_urgency(
    player: Player, available: Sequence[Player], survival_probability: float
) -> float:
    same_position = [candidate for candidate in available if candidate.position == player.position]
    current_tier = [
        candidate.projected_points
        for candidate in same_position
        if candidate.tier == player.tier
    ]
    lower_tiers = [
        candidate.projected_points for candidate in same_position if candidate.tier > player.tier
    ]
    if not lower_tiers:
        return 0.0
    current_floor = min(current_tier) if current_tier else player.projected_points
    next_tier_ceiling = max(lower_tiers)
    cliff = max(0.0, current_floor - next_tier_ceiling)
    remaining_in_tier = max(1, len(current_tier))
    scarcity = 1.0 / math.sqrt(remaining_in_tier)
    return cliff * (1.0 - survival_probability) * scarcity


def picks_until_team_turn(state: DraftState, team_id: str) -> int:
    maximum = state.current_pick + state.team_count * 2
    for pick_number in range(state.current_pick + 1, maximum + 1):
        if team_on_clock(pick_number, state.team_count) == team_id:
            return pick_number - state.current_pick
    return state.team_count


def survival_probability(player: Player, current_pick: int, picks_until_next: int) -> float:
    if player.adp is None:
        return 0.5
    target_pick = current_pick + max(1, picks_until_next)
    spread = max(4.0, player.adp * 0.16)
    return _clamp(1.0 / (1.0 + math.exp((target_pick - player.adp) / spread)), 0.01, 0.99)


def roster_need_multiplier(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    counts = Counter(player.position for player in roster)
    direct_slots = int(settings.roster_slots.get(position.value, 0))
    flex_slots = int(settings.roster_slots.get("FLEX", 0)) if position in FLEX_POSITIONS else 0
    if position in SUPERFLEX_POSITIONS:
        flex_slots += int(
            settings.roster_slots.get("SUPERFLEX", settings.roster_slots.get("SF", 0))
        )
    starter_capacity = direct_slots + flex_slots
    filled = counts[position]
    progress = current_round / max(1, settings.rounds)
    if filled < direct_slots:
        return 1.0 + 0.22 * progress
    if filled < starter_capacity:
        return 1.0 + 0.08 * progress
    bench_count = max(0, filled - starter_capacity)
    return max(0.55, 1.0 - (0.08 + 0.22 * progress) * (bench_count + 1))


def opponent_demand_factor(
    position: Position,
    state: DraftState,
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
) -> float:
    needing = 0
    opponents = 0
    for team_id, player_ids in state.rosters.items():
        if team_id == settings.user_team_id:
            continue
        opponents += 1
        count = sum(
            1
            for player_id in player_ids
            if player_id in players_by_id and players_by_id[player_id].position == position
        )
        if count < int(settings.roster_slots.get(position.value, 0)):
            needing += 1
    return 1.0 if not opponents else 1.0 + 0.15 * needing / opponents


def guardrail_adjustment(
    player: Player,
    player_vorp: float,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    weight = settings.guardrail_weight
    adjustment = 0.0
    if (
        player.position in (Position.QB, Position.TE)
        and int(settings.roster_slots.get("SUPERFLEX", settings.roster_slots.get("SF", 0))) == 0
        and player_vorp < settings.qb_te_vorp_threshold
    ):
        adjustment -= weight * (1.0 - player_vorp / max(1.0, settings.qb_te_vorp_threshold))
    if player.position in (Position.K, Position.DST) and current_round < settings.rounds - 1:
        adjustment -= weight * 3.0
    if player.position in (Position.RB, Position.WR) and current_round >= 4:
        counts = Counter(item.position for item in roster)
        other = Position.WR if player.position == Position.RB else Position.RB
        imbalance = counts[player.position] - counts[other]
        if imbalance >= 2:
            adjustment -= weight * min(1.5, imbalance * 0.25)
        elif imbalance <= -2:
            adjustment += weight * 0.25
    return adjustment


def recommend(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None = None,
    limit: int = 20,
) -> list[RecommendationResult]:
    from .draft import validate_state

    validate_state(state)
    if state.team_count != settings.team_count:
        raise ValueError("draft state and league settings team counts differ")
    validate_state(state)
    if limit < 1:
        raise ValueError("limit must be positive")
    adjustments = adjustments or {}
    drafted_ids = {pick.player_id for pick in state.pick_history}
    adjusted_all = [effective_player(player, adjustments.get(player.id)) for player in players]
    available = [player for player in adjusted_all if player.id not in drafted_ids]
    player_map = {player.id: player for player in adjusted_all}
    levels = replacement_levels(adjusted_all, settings)
    roster = [
        player_map[player_id]
        for player_id in state.rosters.get(settings.user_team_id, ())
        if player_id in player_map
    ]
    current_round = (state.current_pick - 1) // settings.team_count + 1
    until_next = picks_until_team_turn(state, settings.user_team_id)
    scored: list[RecommendationResult] = []
    for player in available:
        player_vorp = vorp(player, levels)
        survival = survival_probability(player, state.current_pick, until_next)
        urgency = tier_cliff_urgency(player, available, survival)
        need = roster_need_multiplier(player.position, roster, settings, current_round)
        # Phase 1.5 will activate the opponent demand model. Keep v1 neutral so
        # recommendation explanations do not imply that opponent behavior was predicted.
        demand = 1.0
        guardrail = guardrail_adjustment(player, player_vorp, roster, settings, current_round)
        adjustment = adjustments.get(player.id)
        opinion = adjustment.points_delta if adjustment else 0.0
        tag_bonus = (
            6.0
            if adjustment and adjustment.tag == "myGuy"
            else -1000.0
            if adjustment and adjustment.tag == "avoid"
            else 0.0
        )
        score = (player_vorp * need * demand) + (urgency * 1.5) + guardrail + tag_bonus
        reasons = _reasons(player_vorp, urgency, survival, need, guardrail, adjustment)
        scored.append(
            RecommendationResult(
                player.id,
                player.name,
                player.position,
                round(score, 4),
                RecommendationLabel.BEST_PICK,
                RecommendationBreakdown(
                    round(player_vorp, 4),
                    round(urgency, 4),
                    round(survival, 4),
                    round(need, 4),
                    round(demand, 4),
                    round(guardrail, 4),
                    round(opinion, 4),
                ),
                reasons,
            )
        )
    scored.sort(
        key=lambda result: (
            -result.dvs_score,
            player_map[result.player_id].adp or float("inf"),
            result.player_id,
        )
    )
    labeled: list[RecommendationResult] = []
    for index, result in enumerate(scored[:limit]):
        breakdown = result.breakdown
        if breakdown.vorp > 20 and breakdown.survival_probability < 0.30:
            label = RecommendationLabel.CANT_PASS
        elif index > 0 and breakdown.survival_probability >= 0.65:
            label = RecommendationLabel.SAFE_TO_WAIT
        else:
            label = RecommendationLabel.BEST_PICK
        labeled.append(replace(result, tier_label=label))
    return labeled


def _reasons(
    player_vorp: float,
    urgency: float,
    survival: float,
    need: float,
    guardrail: float,
    adjustment: UserAdjustment | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if player_vorp > 0:
        reasons.append(f"{player_vorp:.1f} points above replacement")
    if urgency > 2:
        reasons.append("meaningful tier cliff")
    if survival < 0.35:
        reasons.append("unlikely to survive to your next pick")
    elif survival > 0.65:
        reasons.append("likely available at your next pick")
    if need > 1.0:
        reasons.append("fills a roster need")
    if guardrail < 0:
        reasons.append("deprioritized by roster guardrails")
    if adjustment and adjustment.tag:
        reasons.append(f"user tag: {adjustment.tag}")
    return tuple(reasons)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
