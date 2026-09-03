"""Deterministic, side-effect-free Draft Value Score calculations."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from .draft import validate_state
from .lineup import marginal_value
from .models import (
    DraftState,
    FormulaParams,
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
    ir_eligible = player.ir_eligible or adjustment.tag == "irStash"
    return replace(
        player,
        projected_points=player.projected_points + adjustment.points_delta,
        tier=adjustment.tier_override or player.tier,
        ir_eligible=ir_eligible,
    )


def _allocate_weighted_slots(
    total: int, weights: Mapping[Position, float]
) -> dict[Position, int]:
    """Split integer slots by weight using largest-remainder allocation."""
    if total <= 0:
        return {position: 0 for position in weights}
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        return {position: 0 for position in weights}
    scaled = {position: total * weight / weight_sum for position, weight in weights.items()}
    allocated = {position: int(math.floor(value)) for position, value in scaled.items()}
    remainder = total - sum(allocated.values())
    if remainder > 0:
        fractional = sorted(
            ((position, scaled[position] - allocated[position]) for position in weights),
            key=lambda item: (-item[1], item[0].value),
        )
        for index in range(remainder):
            allocated[fractional[index][0]] += 1
    return allocated


def replacement_counts(settings: LeagueSettings) -> dict[Position, int]:
    params = settings.formula_params
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
    flex_weights = {
        Position.RB: float(params.flex_weights.get("RB", 0.45)),
        Position.WR: float(params.flex_weights.get("WR", 0.45)),
        Position.TE: float(params.flex_weights.get("TE", 0.10)),
    }
    for position, added in _allocate_weighted_slots(flex, flex_weights).items():
        counts[position] += added
    superflex = settings.team_count * int(slots.get("SUPERFLEX", slots.get("SF", 0)))
    superflex_weights = {
        Position.QB: float(params.superflex_weights.get("QB", 0.65)),
        Position.RB: float(params.superflex_weights.get("RB", 0.15)),
        Position.WR: float(params.superflex_weights.get("WR", 0.15)),
        Position.TE: float(params.superflex_weights.get("TE", 0.05)),
    }
    for position, added in _allocate_weighted_slots(superflex, superflex_weights).items():
        counts[position] += added
    return {position: max(1, count) for position, count in counts.items()}


def replacement_levels(
    players: Iterable[Player],
    settings: LeagueSettings,
    drafted_by_position: Mapping[Position, int] | None = None,
) -> dict[Position, float]:
    params = settings.formula_params
    counts = replacement_counts(settings)
    if params.demand_adjusted_replacement and drafted_by_position is not None:
        adjusted_counts = {
            position: max(1, counts[position] - drafted_by_position.get(position, 0))
            for position in counts
        }
    else:
        adjusted_counts = counts
    grouped: dict[Position, list[float]] = {position: [] for position in counts}
    for player in players:
        if player.position in grouped:
            grouped[player.position].append(player.projected_points)
    levels: dict[Position, float] = {}
    for position, points in grouped.items():
        ordered = sorted(points, reverse=True)
        replacement_rank = adjusted_counts[position] + params.replacement_index_offset
        index = min(replacement_rank, len(ordered)) - 1
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


def _availability_at_pick(adp: float, pick: int, spread: float) -> float:
    return 1.0 / (1.0 + math.exp((pick - adp) / spread))


def survival_probability(
    player: Player,
    current_pick: int,
    picks_until_next: int,
    params: FormulaParams | None = None,
) -> float:
    """Conditional probability the player is still available at the user's next pick."""
    formula = params or FormulaParams()
    if player.adp is None:
        return formula.survival_default_no_adp
    target_pick = current_pick + max(1, picks_until_next)
    spread = max(formula.survival_spread_min, player.adp * formula.survival_spread_adp_factor)
    available_now = _availability_at_pick(player.adp, current_pick, spread)
    available_next = _availability_at_pick(player.adp, target_pick, spread)
    if available_now <= 0:
        return formula.survival_clamp_low
    conditional = available_next / available_now
    return _clamp(conditional, formula.survival_clamp_low, formula.survival_clamp_high)


def roster_need_multiplier(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    params = settings.formula_params
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
        return 1.0 + params.need_direct_boost * progress
    if filled < starter_capacity:
        return 1.0 + params.need_flex_boost * progress
    bench_count = max(0, filled - starter_capacity)
    return max(
        params.need_floor,
        1.0 - (params.need_bench_penalty_base + params.need_direct_boost * progress)
        * (bench_count + 1),
    )


def _effective_position_cap(position: Position, settings: LeagueSettings) -> int | None:
    params = settings.formula_params
    slots = settings.roster_slots
    superflex = int(slots.get("SUPERFLEX", slots.get("SF", 0)))
    if position == Position.TE:
        return int(params.max_te)
    if position == Position.QB:
        return int(max(params.max_qb, 1 + superflex))
    if position in (Position.K, Position.DST):
        return int(slots.get(position.value, 0))
    return None


def position_caps_map(settings: LeagueSettings) -> dict[Position, int]:
    caps: dict[Position, int] = {}
    for position in (Position.QB, Position.TE, Position.K, Position.DST):
        cap = _effective_position_cap(position, settings)
        if cap is not None:
            caps[position] = cap
    return caps


def _flex_share(position: Position, settings: LeagueSettings) -> float:
    params = settings.formula_params
    slots = settings.roster_slots
    share = 0.0
    flex = int(slots.get("FLEX", 0))
    if flex and position in FLEX_POSITIONS:
        weights = {
            Position.RB: float(params.flex_weights.get("RB", 0.45)),
            Position.WR: float(params.flex_weights.get("WR", 0.45)),
            Position.TE: float(params.flex_weights.get("TE", 0.10)),
        }
        total = sum(weights.values())
        if total > 0:
            share += flex * weights[position] / total
    superflex = int(slots.get("SUPERFLEX", slots.get("SF", 0)))
    if superflex and position in SUPERFLEX_POSITIONS:
        weights = {
            Position.QB: float(params.superflex_weights.get("QB", 0.65)),
            Position.RB: float(params.superflex_weights.get("RB", 0.15)),
            Position.WR: float(params.superflex_weights.get("WR", 0.15)),
            Position.TE: float(params.superflex_weights.get("TE", 0.05)),
        }
        total = sum(weights.values())
        if total > 0:
            share += superflex * weights[position] / total
    return share


def expected_startable_slots(settings: LeagueSettings) -> dict[Position, float]:
    """Weighted direct + FLEX + SUPERFLEX slot counts per position."""
    slots = settings.roster_slots
    startable = {
        Position.QB: float(int(slots.get("QB", 0))),
        Position.RB: float(int(slots.get("RB", 0))),
        Position.WR: float(int(slots.get("WR", 0))),
        Position.TE: float(int(slots.get("TE", 0))),
        Position.K: float(int(slots.get("K", 0))),
        Position.DST: float(int(slots.get("DST", 0))),
    }
    for position in (Position.QB, Position.RB, Position.WR, Position.TE):
        startable[position] += _flex_share(position, settings)
    return startable


def starter_capacity(position: Position, settings: LeagueSettings) -> float:
    direct = int(settings.roster_slots.get(position.value, 0))
    capacity = direct + _flex_share(position, settings)
    cap = _effective_position_cap(position, settings)
    if cap is not None:
        capacity = min(capacity, float(cap))
    return capacity


def depth_target(position: Position, settings: LeagueSettings) -> float:
    capacity = starter_capacity(position, settings)
    cap = _effective_position_cap(position, settings)
    if cap is not None:
        return float(cap)
    bench = int(settings.roster_slots.get("BENCH", 0))
    weights = settings.formula_params.depth_bench_weights
    weight_sum = sum(float(value) for value in weights.values())
    if bench <= 0 or weight_sum <= 0:
        return capacity
    share = bench * float(weights.get(position.value, 0.0)) / weight_sum
    return capacity + share


def _open_required_starters(counts: Mapping[Position, int], settings: LeagueSettings) -> int:
    open_required = 0
    for position in (
        Position.QB,
        Position.RB,
        Position.WR,
        Position.TE,
    ):
        required = int(settings.roster_slots.get(position.value, 0))
        cap = _effective_position_cap(position, settings)
        if cap is not None:
            required = min(required, cap)
        open_required += max(0, required - int(counts.get(position, 0)))
    return open_required


def roster_shape_need(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    """V3 roster-construction need: starter holes, RB/WR balance, and depth targets."""
    params = settings.formula_params
    counts = Counter(player.position for player in roster)
    filled = counts[position]
    direct = int(settings.roster_slots.get(position.value, 0))
    capacity = starter_capacity(position, settings)
    target = max(1e-6, depth_target(position, settings))
    progress = current_round / max(1, settings.rounds)
    remaining_picks = max(1, settings.rounds - current_round + 1)
    need = 1.0

    if filled < direct:
        slot_share = (direct - filled) / max(1, direct)
        need += params.need_starter_boost * (1.0 + progress) * (0.5 + 0.5 * slot_share)
    elif filled < capacity:
        span = max(1e-6, capacity - direct)
        need += params.need_flex_boost_v3 * (1.0 + progress) * ((capacity - filled) / span)
    elif filled < target:
        span = max(1e-6, target - capacity)
        need += params.need_depth_boost * ((target - filled) / span)
    else:
        need -= params.need_over_target_penalty * ((filled - target) + 1.0)

    if position in (Position.RB, Position.WR):
        rb_target = max(1e-6, depth_target(Position.RB, settings))
        wr_target = max(1e-6, depth_target(Position.WR, settings))
        rb_ratio = counts[Position.RB] / rb_target
        wr_ratio = counts[Position.WR] / wr_target
        mean_ratio = (rb_ratio + wr_ratio) / 2.0
        fill_ratio = filled / target
        need += params.need_balance_weight * (mean_ratio - fill_ratio)

    if filled >= capacity:
        open_required = _open_required_starters(counts, settings)
        if open_required > 0:
            need -= params.need_duplicate_penalty * min(1.0, open_required / remaining_picks)

    return _clamp(need, params.need_v3_floor, params.need_v3_ceiling)


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
    if not opponents:
        return 1.0
    return 1.0 + settings.formula_params.opponent_demand_weight * needing / opponents


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
    if player.position in (Position.K, Position.DST):
        from .special_teams import special_teams_status

        status = special_teams_status(
            player, roster, settings, current_round, settings.formula_params
        )
        if status.timing_penalty < 0:
            adjustment += status.timing_penalty
    if player.position in (Position.RB, Position.WR) and current_round >= 4:
        counts = Counter(item.position for item in roster)
        other = Position.WR if player.position == Position.RB else Position.RB
        imbalance = counts[player.position] - counts[other]
        if imbalance >= 2:
            adjustment -= weight * min(1.5, imbalance * 0.25)
        elif imbalance <= -2:
            adjustment += weight * 0.25
    if settings.formula_params.formula_version >= 3:
        params = settings.formula_params
        counts = Counter(item.position for item in roster)
        if player.position == Position.TE and counts[Position.TE] >= params.max_te:
            adjustment -= weight * params.position_cap_penalty_multiple
        elif player.position == Position.QB:
            superflex = int(
                settings.roster_slots.get("SUPERFLEX", settings.roster_slots.get("SF", 0))
            )
            cap = max(params.max_qb, 1 + superflex)
            if counts[Position.QB] >= cap:
                late_window = (
                    settings.team_count >= params.backup_qb_min_team_count
                    and current_round > settings.rounds - params.backup_qb_final_rounds
                )
                multiple = (
                    params.backup_qb_window_penalty_multiple
                    if late_window
                    else params.position_cap_penalty_multiple
                )
                adjustment -= weight * multiple
    return adjustment


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


def wait_loss(
    player: Player,
    available: Sequence[Player],
    marginals: Mapping[str, float],
    survival_by_id: Mapping[str, float],
) -> float:
    marginal = marginals.get(player.id, 0.0)
    fallback = expected_fallback_value(player, available, marginals, survival_by_id)
    return max(0.0, marginal - fallback)


def recommend(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None = None,
    limit: int = 20,
) -> list[RecommendationResult]:
    validate_state(state)
    if state.team_count != settings.team_count:
        raise ValueError("draft state and league settings team counts differ")
    if limit < 1:
        raise ValueError("limit must be positive")
    params = settings.formula_params
    if params.formula_version == 1:
        return _recommend_v1(players, state, settings, adjustments, limit)
    if params.formula_version == 2:
        return _recommend_v2(players, state, settings, adjustments, limit)
    if params.formula_version == 3:
        return _recommend_v3(players, state, settings, adjustments, limit)
    if params.formula_version == 4:
        from .v4 import recommend_v4

        return recommend_v4(players, state, settings, adjustments, limit)
    if params.formula_version == 5:
        from .v5 import recommend_v5

        return recommend_v5(players, state, settings, adjustments, limit)
    from .v4 import recommend_v4

    return recommend_v4(players, state, settings, adjustments, limit)


def _recommend_v1(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None,
    limit: int,
) -> list[RecommendationResult]:
    params = settings.formula_params
    adjustments = adjustments or {}
    drafted_ids = state.drafted_ids
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
        survival = survival_probability(player, state.current_pick, until_next, params)
        urgency = tier_cliff_urgency(player, available, survival)
        need = roster_need_multiplier(player.position, roster, settings, current_round)
        # Phase 1.5 will activate the opponent demand model. Keep v1 neutral so
        # recommendation explanations do not imply that opponent behavior was predicted.
        demand = 1.0
        guardrail = guardrail_adjustment(player, player_vorp, roster, settings, current_round)
        adjustment = adjustments.get(player.id)
        opinion = adjustment.points_delta if adjustment else 0.0
        tag_bonus = (
            params.my_guy_bonus
            if adjustment and adjustment.tag == "myGuy"
            else 0.0
        )
        if adjustment and adjustment.tag == "avoid":
            continue
        value_vorp = max(0.0, player_vorp)
        score = (
            (value_vorp * need * demand)
            + (urgency * params.urgency_weight)
            + guardrail
            + tag_bonus
        )
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
        if (
            breakdown.vorp > params.cant_pass_vorp_min
            and breakdown.survival_probability < params.cant_pass_survival_max
        ):
            label = RecommendationLabel.CANT_PASS
        elif index > 0 and breakdown.survival_probability >= params.safe_to_wait_survival_min:
            label = RecommendationLabel.SAFE_TO_WAIT
        else:
            label = RecommendationLabel.BEST_PICK
        labeled.append(replace(result, tier_label=label))
    return labeled


def _recommend_v2(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None,
    limit: int,
) -> list[RecommendationResult]:
    params = settings.formula_params
    adjustments = adjustments or {}
    drafted_ids = state.drafted_ids
    adjusted_all = [effective_player(player, adjustments.get(player.id)) for player in players]
    available = [player for player in adjusted_all if player.id not in drafted_ids]
    if params.exclude_avoid_tag:
        available = [
            player
            for player in available
            if adjustments.get(player.id) is None or adjustments[player.id].tag != "avoid"
        ]
    player_map = {player.id: player for player in adjusted_all}
    levels = replacement_levels(adjusted_all, settings)
    roster = [
        player_map[player_id]
        for player_id in state.rosters.get(settings.user_team_id, ())
        if player_id in player_map
    ]
    current_round = (state.current_pick - 1) // settings.team_count + 1
    until_next = picks_until_team_turn(state, settings.user_team_id)
    marginals = {
        player.id: marginal_value(player, roster, settings, levels, params) for player in available
    }
    survival_by_id = {
        player.id: survival_probability(player, state.current_pick, until_next, params)
        for player in available
    }
    scored: list[RecommendationResult] = []
    for player in available:
        player_vorp = vorp(player, levels)
        survival = survival_by_id[player.id]
        marginal = marginals[player.id]
        loss = wait_loss(player, available, marginals, survival_by_id)
        cliff = tier_cliff_urgency(player, available, survival)
        demand = 1.0
        guardrail = guardrail_adjustment(player, marginal, roster, settings, current_round)
        adjustment = adjustments.get(player.id)
        opinion = adjustment.points_delta if adjustment else 0.0
        tag_bonus = params.my_guy_bonus if adjustment and adjustment.tag == "myGuy" else 0.0
        score = marginal + (params.wait_loss_weight * loss) + guardrail + tag_bonus
        reasons = _reasons_v2(player_vorp, marginal, loss, cliff, survival, guardrail, adjustment)
        scored.append(
            RecommendationResult(
                player.id,
                player.name,
                player.position,
                round(score, 4),
                RecommendationLabel.BEST_PICK,
                RecommendationBreakdown(
                    round(player_vorp, 4),
                    round(cliff, 4),
                    round(survival, 4),
                    1.0,
                    round(demand, 4),
                    round(guardrail, 4),
                    round(opinion, 4),
                    round(marginal, 4),
                    round(loss, 4),
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
        if (
            breakdown.marginal_value >= params.value_min
            and breakdown.wait_loss >= params.urgent_wait_loss
        ):
            label = RecommendationLabel.CANT_PASS
        elif (
            index > 0
            and breakdown.survival_probability >= params.safe_to_wait_survival_min
            and breakdown.wait_loss <= params.safe_wait_loss
        ):
            label = RecommendationLabel.SAFE_TO_WAIT
        else:
            label = RecommendationLabel.BEST_PICK
        labeled.append(replace(result, tier_label=label))
    return labeled


def _recommend_v3(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None,
    limit: int,
) -> list[RecommendationResult]:
    params = settings.formula_params
    adjustments = adjustments or {}
    drafted_ids = state.drafted_ids
    adjusted_all = [effective_player(player, adjustments.get(player.id)) for player in players]
    available = [player for player in adjusted_all if player.id not in drafted_ids]
    if params.exclude_avoid_tag:
        available = [
            player
            for player in available
            if adjustments.get(player.id) is None or adjustments[player.id].tag != "avoid"
        ]
    player_map = {player.id: player for player in adjusted_all}
    levels = replacement_levels(adjusted_all, settings)
    roster = [
        player_map[player_id]
        for player_id in state.rosters.get(settings.user_team_id, ())
        if player_id in player_map
    ]
    current_round = (state.current_pick - 1) // settings.team_count + 1
    until_next = picks_until_team_turn(state, settings.user_team_id)
    caps = position_caps_map(settings)
    marginals = {
        player.id: marginal_value(player, roster, settings, levels, params, caps)
        for player in available
    }
    survival_by_id = {
        player.id: survival_probability(player, state.current_pick, until_next, params)
        for player in available
    }
    raw_need_by_id = {
        player.id: roster_shape_need(player.position, roster, settings, current_round)
        for player in available
    }
    loss_by_id = {
        player.id: wait_loss(player, available, marginals, survival_by_id) for player in available
    }
    base_by_id = {
        player.id: marginals[player.id] + params.wait_loss_weight * loss_by_id[player.id]
        for player in available
    }
    needed_bases = [
        base_by_id[player.id] for player in available if raw_need_by_id[player.id] >= 1.0
    ]
    best_needed_base = max(needed_bases) if needed_bases else None
    scored: list[RecommendationResult] = []
    for player in available:
        player_vorp = vorp(player, levels)
        survival = survival_by_id[player.id]
        marginal = marginals[player.id]
        loss = loss_by_id[player.id]
        cliff = tier_cliff_urgency(player, available, survival)
        demand = 1.0
        guardrail = guardrail_adjustment(player, marginal, roster, settings, current_round)
        need = raw_need_by_id[player.id]
        base = base_by_id[player.id]
        overridden = False
        if (
            best_needed_base is not None
            and base - best_needed_base >= params.need_override_points
            and need < 1.0
        ):
            need = 1.0
            overridden = True
        adjustment = adjustments.get(player.id)
        opinion = adjustment.points_delta if adjustment else 0.0
        tag_bonus = params.my_guy_bonus if adjustment and adjustment.tag == "myGuy" else 0.0
        score = (base * need) + guardrail + tag_bonus
        reasons = _reasons_v3(
            player,
            player_vorp,
            marginal,
            loss,
            cliff,
            survival,
            need,
            guardrail,
            adjustment,
            roster,
            settings,
            current_round,
            overridden,
        )
        scored.append(
            RecommendationResult(
                player.id,
                player.name,
                player.position,
                round(score, 4),
                RecommendationLabel.BEST_PICK,
                RecommendationBreakdown(
                    round(player_vorp, 4),
                    round(cliff, 4),
                    round(survival, 4),
                    round(need, 4),
                    round(demand, 4),
                    round(guardrail, 4),
                    round(opinion, 4),
                    round(marginal, 4),
                    round(loss, 4),
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
        if (
            breakdown.marginal_value >= params.value_min
            and breakdown.wait_loss >= params.urgent_wait_loss
        ):
            label = RecommendationLabel.CANT_PASS
        elif (
            index > 0
            and breakdown.survival_probability >= params.safe_to_wait_survival_min
            and breakdown.wait_loss <= params.safe_wait_loss
        ):
            label = RecommendationLabel.SAFE_TO_WAIT
        else:
            label = RecommendationLabel.BEST_PICK
        labeled.append(replace(result, tier_label=label))
    return labeled


def _reasons_v3(
    player: Player,
    player_vorp: float,
    marginal: float,
    loss: float,
    cliff: float,
    survival: float,
    need: float,
    guardrail: float,
    adjustment: UserAdjustment | None,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    overridden: bool,
) -> tuple[str, ...]:
    reasons = list(
        _reasons_v2(player_vorp, marginal, loss, cliff, survival, guardrail, adjustment)
    )
    counts = Counter(item.position for item in roster)
    direct = int(settings.roster_slots.get(player.position.value, 0))
    if overridden:
        reasons.append("elite value overrides roster need")
    elif need > 1.05:
        if counts[player.position] < direct:
            reasons.append("fills an open starter slot")
        else:
            reasons.append("fills a roster need")
    elif need < 0.9:
        reasons.append("position already filled")
    if player.position == Position.TE and counts[Position.TE] >= settings.formula_params.max_te:
        reasons.append("roster already has a TE")
    if player.position == Position.QB:
        cap = _effective_position_cap(Position.QB, settings) or settings.formula_params.max_qb
        if counts[Position.QB] >= cap:
            late_window = (
                settings.team_count >= settings.formula_params.backup_qb_min_team_count
                and current_round
                > settings.rounds - settings.formula_params.backup_qb_final_rounds
            )
            if late_window:
                reasons.append("backup QB only late")
    return tuple(reasons)


def _reasons_v2(
    player_vorp: float,
    marginal: float,
    loss: float,
    cliff: float,
    survival: float,
    guardrail: float,
    adjustment: UserAdjustment | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if marginal > 0:
        reasons.append(f"{marginal:.1f} marginal roster points")
    if player_vorp > 0:
        reasons.append(f"{player_vorp:.1f} points above replacement")
    if loss >= 3:
        reasons.append("meaningful expected loss if you wait")
    elif cliff > 2:
        reasons.append("meaningful tier cliff")
    if survival < 0.35:
        reasons.append("unlikely to survive to your next pick")
    elif survival > 0.65:
        reasons.append("likely available at your next pick")
    if guardrail < 0:
        reasons.append("deprioritized by roster guardrails")
    if adjustment and adjustment.tag:
        reasons.append(f"user tag: {adjustment.tag}")
    return tuple(reasons)


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
