"""Late-round upside, handcuff, and IR stash signals for V4.1."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .lineup import _position_surplus
from .models import FormulaParams, LeagueSettings, Player, Position
from .phase import DraftPhase, player_fills_open_starter


@dataclass(frozen=True, slots=True)
class OptionalityResult:
    late_round_upside: float
    contingent_value: float
    handcuff_bonus: float
    ir_stash_value: float
    optionality_value: float
    reason: str | None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _depth_confidence(player: Player, params: FormulaParams) -> float:
    source = (player.depth_chart_source or "derived").lower()
    if source == "official":
        return 1.0
    return params.handcuff_derived_depth_confidence


def _risk_modifier(starter: Player, params: FormulaParams) -> float:
    if starter.risk_score is None:
        return 1.0
    raw = 1.0 + params.handcuff_risk_sensitivity * (starter.risk_score - 5.0) / 5.0
    return _clamp(
        raw,
        params.handcuff_risk_modifier_min,
        params.handcuff_risk_modifier_max,
    )


def _role_probability(starter: Player, params: FormulaParams) -> float:
    return (
        params.handcuff_base_role_probability
        * _risk_modifier(starter, params)
        * _depth_confidence(starter, params)
    )


def _team_starters_by_position(
    roster: Sequence[Player],
) -> dict[tuple[str, Position], list[Player]]:
    grouped: dict[tuple[str, Position], list[Player]] = defaultdict(list)
    for player in roster:
        if not player.team:
            continue
        grouped[(player.team.upper(), player.position)].append(player)
    for _, players in grouped.items():
        players.sort(
            key=lambda item: (
                item.depth_chart_rank if item.depth_chart_rank is not None else 999,
                -item.projected_points,
            )
        )
    return grouped


def late_round_upside(
    player: Player,
    phase: DraftPhase,
    params: FormulaParams,
    levels: Mapping[Position, float],
) -> tuple[float, str | None]:
    if player.upside_score is None or phase.late_weight <= 0.0:
        return 0.0, None
    upside_index = _clamp(
        (player.upside_score - params.upside_reference_score) / params.upside_score_span,
        0.0,
        1.0,
    )
    if player.is_rookie:
        upside_index = min(1.0, upside_index + params.rookie_upside_bonus)
    if player.is_breakout:
        upside_index = min(1.0, upside_index + params.breakout_upside_bonus)
    if upside_index <= 0.0:
        return 0.0, None
    damp = params.upside_starter_damp if player_fills_open_starter(
        player, phase.open_starter_slots
    ) else 1.0
    points = phase.late_weight * params.upside_weight_max * upside_index * damp
    if points < 0.25:
        return 0.0, None
    return points, "high-upside late-round bench option"


def contingent_value(
    player: Player,
    roster: Sequence[Player],
    phase: DraftPhase,
    params: FormulaParams,
    levels: Mapping[Position, float],
) -> tuple[float, float, str | None]:
    if phase.late_weight <= 0.0:
        return 0.0, 0.0, None
    if player.position.value not in params.handcuff_positions:
        return 0.0, 0.0, None
    if (
        player.depth_chart_rank is not None
        and player.depth_chart_rank > params.handcuff_max_depth_rank
    ):
        return 0.0, 0.0, None
    if not player.team:
        return 0.0, 0.0, None

    starters = _team_starters_by_position(roster)
    team_key = player.team.upper()
    team_starters = starters.get((team_key, player.position), [])
    if not team_starters:
        return 0.0, 0.0, None

    starter = team_starters[0]
    if starter.id == player.id:
        return 0.0, 0.0, None
    if _position_surplus(starter, levels) < params.handcuff_min_starter_surplus:
        return 0.0, 0.0, None

    inherited = params.handcuff_inherit_share * _position_surplus(starter, levels)
    already_own = _position_surplus(player, levels)
    role_prob = _role_probability(starter, params) * _depth_confidence(player, params)
    contingent = role_prob * max(0.0, inherited - already_own)
    if contingent <= 0.0:
        return 0.0, 0.0, None

    scale = params.handcuff_weight_max / max(params.upside_weight_max, 1e-6)
    bonus = min(
        params.handcuff_max_bonus,
        phase.late_weight * scale * contingent,
    )
    if bonus < params.handcuff_min_reason_points:
        return contingent, 0.0, None
    return contingent, bonus, "direct backup to your RB1 with meaningful contingent upside"


def ir_stash_value(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    phase: DraftPhase,
    params: FormulaParams,
) -> tuple[float, str | None]:
    if settings.ir_slots <= 0 or phase.late_weight <= 0.0:
        return 0.0, None
    if current_round <= settings.rounds - params.ir_stash_final_rounds:
        return 0.0, None

    ir_eligible = player.ir_eligible
    if not ir_eligible and player.injury_status:
        status = player.injury_status.upper()
        ir_eligible = status in {"IR", "OUT", "PUP", "NFI", "SUSP"}
    if not ir_eligible:
        return 0.0, None

    ir_statuses = {"IR", "OUT", "PUP", "NFI", "SUSP"}
    occupied = sum(
        1
        for item in roster
        if item.ir_eligible
        or (item.injury_status and item.injury_status.upper() in ir_statuses)
    )
    open_slots = max(0, settings.ir_slots - occupied)
    if open_slots <= 0:
        return 0.0, None

    upside = player.upside_score or 0.0
    if upside <= params.upside_reference_score:
        return 0.0, None

    return_discount = 1.0
    if player.expected_return_week is not None:
        return_discount = _clamp(
            1.0 - (player.expected_return_week - 1) / max(1, params.ir_return_week_horizon),
            0.25,
            1.0,
        )

    upside_index = _clamp(
        (upside - params.upside_reference_score) / params.upside_score_span,
        0.0,
        1.0,
    )
    points = min(
        params.ir_stash_max_bonus,
        phase.late_weight * params.ir_stash_weight * upside_index * return_discount,
    )
    if points < 0.5:
        return 0.0, None
    return points, "IR stash with an available IR slot"


def optionality_for_player(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    phase: DraftPhase,
    params: FormulaParams,
    current_round: int,
) -> OptionalityResult:
    upside, upside_reason = late_round_upside(player, phase, params, levels)
    contingent, handcuff, handcuff_reason = contingent_value(
        player, roster, phase, params, levels
    )
    ir_value, ir_reason = ir_stash_value(
        player, roster, settings, current_round, phase, params
    )

    components = [
        (upside, upside_reason),
        (handcuff, handcuff_reason),
        (ir_value, ir_reason),
    ]
    if params.optionality_combine == "sum":
        total = sum(value for value, _ in components)
        reason = next((text for value, text in components if text and value > 0), None)
    else:
        best = max(components, key=lambda item: item[0])
        total = best[0]
        reason = best[1] if best[0] > 0 else None

    return OptionalityResult(
        late_round_upside=upside,
        contingent_value=contingent,
        handcuff_bonus=handcuff,
        ir_stash_value=ir_value,
        optionality_value=total,
        reason=reason,
    )
