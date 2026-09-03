"""V5-only roster policy: negative VORP, soft bench balance, reliability."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from .formula import (
    depth_target,
    starter_capacity,
    vorp,
)
from .lineup import _position_surplus
from .models import LeagueSettings, Player, Position, V5FormulaParams
from .phase import DraftPhase, player_fills_open_starter
from .v4 import shape_adjustment


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _open_required_starters(counts: Mapping[Position, int], settings: LeagueSettings) -> int:
    from .formula import _effective_position_cap

    open_required = 0
    for position in (Position.QB, Position.RB, Position.WR, Position.TE):
        required = int(settings.roster_slots.get(position.value, 0))
        cap = _effective_position_cap(position, settings)
        if cap is not None:
            required = min(required, cap)
        open_required += max(0, required - int(counts.get(position, 0)))
    return open_required


def roster_shape_need_without_balance(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    """Reproduce V4 roster_shape_need without the RB/WR balance term."""
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

    if filled >= capacity:
        open_required = _open_required_starters(counts, settings)
        if open_required > 0:
            need -= params.need_duplicate_penalty * min(1.0, open_required / remaining_picks)

    return _clamp(need, params.need_v3_floor, params.need_v3_ceiling)


def shape_without_rigid_balance(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    params: V5FormulaParams,
) -> float:
    need = roster_shape_need_without_balance(position, roster, settings, current_round)
    raw = params.need_points_scale * (need - 1.0)
    return _clamp(raw, -params.need_points_cap, params.need_points_cap)


def legacy_rb_wr_guardrail_component(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    if player.position not in (Position.RB, Position.WR) or current_round < 4:
        return 0.0
    weight = settings.guardrail_weight
    counts = Counter(item.position for item in roster)
    other = Position.WR if player.position == Position.RB else Position.RB
    imbalance = counts[player.position] - counts[other]
    if imbalance >= 2:
        return -weight * min(1.5, imbalance * 0.25)
    if imbalance <= -2:
        return weight * 0.25
    return 0.0


def compose_shape_for_v5(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    params: V5FormulaParams,
    late_phase_weight: float,
) -> float:
    legacy = shape_adjustment(position, roster, settings, current_round, params)
    alt = shape_without_rigid_balance(position, roster, settings, current_round, params)
    blend = params.v5_policy_strength * late_phase_weight
    return legacy + blend * (alt - legacy)


def compose_guardrail_for_v5(
    player: Player,
    player_vorp: float,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    params: V5FormulaParams,
    late_phase_weight: float,
) -> float:
    from .formula import guardrail_adjustment

    legacy = guardrail_adjustment(player, player_vorp, roster, settings, current_round)
    rb_wr = legacy_rb_wr_guardrail_component(player, roster, settings, current_round)
    blend = params.v5_policy_strength * late_phase_weight
    return legacy - blend * rb_wr


def negative_vorp_adjustment(
    player: Player,
    player_vorp: float,
    replacement_level: float,
    phase: DraftPhase,
    params: V5FormulaParams,
) -> float:
    if player.position in (Position.K, Position.DST):
        return 0.0
    if player_vorp >= 0.0 or params.v5_policy_strength <= 0.0 or phase.late_weight <= 0.0:
        return 0.0
    ratio = max(0.0, -player_vorp / max(replacement_level, 1.0))
    role_factor = (
        params.negative_vorp_starter_damp
        if player_fills_open_starter(player, phase.open_starter_slots)
        else 1.0
    )
    penalty = min(
        params.negative_vorp_bench_cap,
        params.negative_vorp_bench_weight * ratio * phase.late_weight * role_factor,
    )
    return -params.v5_policy_strength * penalty


def usable_quality_weight(
    player: Player,
    levels: Mapping[Position, float],
    params: V5FormulaParams,
) -> float:
    replacement = levels.get(player.position, 0.0)
    if replacement <= 0.0:
        return 1.0 if player.projected_points >= 0 else 0.0
    vorp_ratio = (player.projected_points - replacement) / replacement
    floor = params.bench_balance_usable_vorp_floor_ratio
    if vorp_ratio >= 0.0:
        return 1.0
    if vorp_ratio <= floor:
        return 0.0
    return (vorp_ratio - floor) / (0.0 - floor)


def usable_depth(
    roster: Sequence[Player],
    position: Position,
    levels: Mapping[Position, float],
    params: V5FormulaParams,
) -> float:
    return sum(
        usable_quality_weight(player, levels, params)
        for player in roster
        if player.position == position
    )


def _rb_wr_target_share(settings: LeagueSettings) -> tuple[float, float]:
    params = settings.formula_params
    weights = params.depth_bench_weights
    rb_w = float(weights.get("RB", 0.5))
    wr_w = float(weights.get("WR", 0.5))
    total = rb_w + wr_w
    if total <= 0:
        return 0.5, 0.5
    return rb_w / total, wr_w / total


def _healthy_depth_floor(settings: LeagueSettings, params: V5FormulaParams) -> tuple[float, float]:
    rb_share, wr_share = _rb_wr_target_share(settings)
    rb_direct = float(int(settings.roster_slots.get("RB", 0)))
    wr_direct = float(int(settings.roster_slots.get("WR", 0)))
    rb_flex = starter_capacity(Position.RB, settings) - rb_direct
    wr_flex = starter_capacity(Position.WR, settings) - wr_direct
    reserve = params_reserve_slots(settings, params) * 0.5
    rb_floor = rb_direct + rb_flex + reserve * (rb_share / max(rb_share + wr_share, 1e-6))
    wr_floor = wr_direct + wr_flex + reserve * (wr_share / max(rb_share + wr_share, 1e-6))
    return rb_floor, wr_floor


def params_reserve_slots(settings: LeagueSettings, params: V5FormulaParams) -> float:
    bench = int(settings.roster_slots.get("BENCH", 0))
    if bench <= 0:
        return 0.0
    reserve = float(params.bench_balance_reserve_slots)
    return reserve * min(1.0, bench / 6.0)


def _band_distance(rb_ratio: float, wr_ratio: float, center: float, half_width: float) -> float:
    total = rb_ratio + wr_ratio
    if total <= 0:
        return 0.0
    share = rb_ratio / total
    if abs(share - center) <= half_width:
        return 0.0
    return abs(share - center) - half_width


def bench_balance_adjustment(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    phase: DraftPhase,
    params: V5FormulaParams,
) -> tuple[float, float, float]:
    if params.v5_policy_strength <= 0.0 or phase.late_weight <= 0.0:
        return 0.0, 0.0, 0.0
    bench = int(settings.roster_slots.get("BENCH", 0))
    if bench <= 0:
        return 0.0, 0.0, 0.0

    rb_depth = usable_depth(roster, Position.RB, levels, params)
    wr_depth = usable_depth(roster, Position.WR, levels, params)
    rb_floor, wr_floor = _healthy_depth_floor(settings, params)
    if rb_depth >= rb_floor and wr_depth >= wr_floor:
        before = _band_distance(rb_depth, wr_depth, 0.5, params.bench_balance_band_half_width)
    else:
        before = 0.0

    hypothetical = [*roster, player]
    rb_after = usable_depth(hypothetical, Position.RB, levels, params)
    wr_after = usable_depth(hypothetical, Position.WR, levels, params)
    if rb_after >= rb_floor and wr_after >= wr_floor:
        after = _band_distance(rb_after, wr_after, 0.5, params.bench_balance_band_half_width)
    else:
        after = 0.0

    delta = before - after
    adjustment = _clamp(
        delta * params.bench_balance_max_adjustment * phase.late_weight,
        -params.bench_balance_max_adjustment,
        params.bench_balance_max_adjustment,
    )
    return (
        params.v5_policy_strength * adjustment,
        rb_depth,
        wr_depth,
    )


def _surplus(player: Player, levels: Mapping[Position, float]) -> float:
    return _position_surplus(player, levels)


def roster_risk_score(
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    params: V5FormulaParams,
) -> float:
    if not roster:
        return params.reliability_target_risk

    rb_wr_te = [p for p in roster if p.position in (Position.RB, Position.WR, Position.TE)]
    if not rb_wr_te:
        return params.reliability_target_risk

    by_surplus = sorted(rb_wr_te, key=lambda p: _surplus(p, levels), reverse=True)
    direct_rb = int(settings.roster_slots.get("RB", 0))
    direct_wr = int(settings.roster_slots.get("WR", 0))
    direct_te = int(settings.roster_slots.get("TE", 0))
    flex_slots = int(settings.roster_slots.get("FLEX", 0))

    weighted: list[tuple[float, float]] = []
    rb_taken = wr_taken = te_taken = flex_taken = 0
    reserve_remaining = params.reliability_reserve_slots
    for player in by_surplus:
        if player.risk_score is None:
            continue
        weight = 0.0
        if player.position == Position.RB and rb_taken < direct_rb:
            rb_taken += 1
            weight = 1.0
        elif player.position == Position.WR and wr_taken < direct_wr:
            wr_taken += 1
            weight = 1.0
        elif player.position == Position.TE and te_taken < direct_te:
            te_taken += 1
            weight = 1.0
        elif flex_taken < flex_slots and player.position in (
            Position.RB,
            Position.WR,
            Position.TE,
        ):
            flex_taken += 1
            weight = params.reliability_flex_weight
        elif reserve_remaining > 0:
            weight = params.reliability_reserve_weight
            reserve_remaining -= 1
        if weight > 0:
            weighted.append((player.risk_score, weight))

    if len(weighted) < params.reliability_min_known_players:
        return params.reliability_target_risk
    total_weight = sum(w for _, w in weighted)
    if total_weight <= 0:
        return params.reliability_target_risk
    return sum(score * weight for score, weight in weighted) / total_weight


def raw_reliability_fit(
    candidate: Player,
    roster_risk: float,
    phase: DraftPhase,
    params: V5FormulaParams,
) -> float:
    if candidate.risk_score is None or params.v5_policy_strength <= 0.0:
        return 0.0
    if phase.late_weight <= 0.0:
        return 0.0
    if candidate.position not in (Position.RB, Position.WR, Position.TE):
        return 0.0
    span = max(1e-6, params.reliability_risk_span)
    roster_signal = _clamp((roster_risk - params.reliability_target_risk) / span, -1.0, 1.0)
    candidate_signal = _clamp(
        (params.reliability_target_risk - candidate.risk_score) / span, -1.0, 1.0
    )
    raw = params.reliability_weight_max * phase.late_weight * roster_signal * candidate_signal
    return _clamp(raw, -params.reliability_weight_max, params.reliability_weight_max)


def apply_reliability_buckets(
    scores: dict[str, float],
    fits: dict[str, float],
    params: V5FormulaParams,
) -> dict[str, float]:
    if params.v5_policy_strength <= 0.0:
        return {player_id: 0.0 for player_id in scores}

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    adjustments: dict[str, float] = {player_id: 0.0 for player_id in scores}
    index = 0
    threshold = params.reliability_close_score_threshold

    while index < len(ordered):
        anchor_id, anchor_score = ordered[index]
        bucket = [anchor_id]
        cursor = index + 1
        while cursor < len(ordered):
            candidate_id, candidate_score = ordered[cursor]
            if anchor_score - candidate_score <= threshold:
                bucket.append(candidate_id)
                cursor += 1
            else:
                break
        if len(bucket) >= 2:
            for player_id in bucket:
                adjustments[player_id] = params.v5_policy_strength * fits.get(player_id, 0.0)
        index = cursor if cursor > index + 1 else index + 1

    return adjustments
