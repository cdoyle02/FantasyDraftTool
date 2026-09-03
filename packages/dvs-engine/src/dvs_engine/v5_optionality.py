"""V5 own-handcuff classification, league scaling, and optionality recombination."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .lineup import _position_surplus
from .models import LeagueSettings, Player, Position, V5FormulaParams
from .optionality import (
    OptionalityResult,
    _depth_confidence,
    _role_probability,
    _team_starters_by_position,
    contingent_value,
    ir_stash_value,
    late_round_upside,
)
from .phase import DraftPhase


@dataclass(frozen=True, slots=True)
class V5OptionalityResult:
    late_round_upside: float
    contingent_value: float
    handcuff_bonus: float
    ir_stash_value: float
    optionality_value: float
    reason: str | None
    raw_handcuff_bonus: float
    adjusted_handcuff_bonus: float
    own_handcuff_league_multiplier: float
    own_handcuff_count: int
    own_handcuff_count_multiplier: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def is_own_handcuff_candidate(
    player: Player,
    roster: Sequence[Player],
    levels: Mapping[Position, float],
    params: V5FormulaParams,
) -> tuple[bool, Player | None]:
    if player.position.value not in params.handcuff_positions:
        return False, None
    if (
        player.depth_chart_rank is not None
        and player.depth_chart_rank > params.handcuff_max_depth_rank
    ):
        return False, None
    if not player.team:
        return False, None

    starters = _team_starters_by_position(roster)
    team_key = player.team.upper()
    team_starters = starters.get((team_key, player.position), [])
    if not team_starters:
        return False, None

    starter = team_starters[0]
    if starter.id == player.id:
        return False, None
    if starter.depth_chart_rank != 1:
        return False, None
    if _position_surplus(starter, levels) < params.handcuff_min_starter_surplus:
        return False, None
    return True, starter


def count_rostered_own_handcuffs(
    roster: Sequence[Player],
    levels: Mapping[Position, float],
    params: V5FormulaParams,
) -> int:
    count = 0
    for player in roster:
        is_own, _ = is_own_handcuff_candidate(player, roster, levels, params)
        if is_own:
            count += 1
    return count


def league_handcuff_multiplier(team_count: int, params: V5FormulaParams) -> float:
    anchors = (
        (8, params.own_handcuff_factor_8_team),
        (10, params.own_handcuff_factor_10_team),
        (12, params.own_handcuff_factor_12_team),
        (14, params.own_handcuff_factor_14_team),
    )
    if team_count <= anchors[0][0]:
        return anchors[0][1]
    if team_count >= anchors[-1][0]:
        return anchors[-1][1]
    for (low_count, low_factor), (high_count, high_factor) in zip(
        anchors, anchors[1:], strict=False
    ):
        if low_count <= team_count <= high_count:
            span = high_count - low_count
            if span <= 0:
                return low_factor
            t = (team_count - low_count) / span
            return low_factor + t * (high_factor - low_factor)
    return params.own_handcuff_factor_12_team


def own_handcuff_count_multiplier(
    existing_count: int,
    params: V5FormulaParams,
) -> float:
    if existing_count <= 0:
        return 1.0
    if existing_count == 1:
        return params.own_handcuff_second_multiplier
    if existing_count == 2:
        return params.own_handcuff_third_multiplier
    return params.own_handcuff_fourth_plus_multiplier


def adjust_handcuff_bonus(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    raw_bonus: float,
    params: V5FormulaParams,
) -> tuple[float, float, int, float, str | None]:
    if raw_bonus <= 0.0:
        return 0.0, 0.0, 0, 1.0, None

    is_own, _ = is_own_handcuff_candidate(player, roster, levels, params)
    if not is_own:
        return raw_bonus, raw_bonus, 0, 1.0, None

    league_mult = league_handcuff_multiplier(settings.team_count, params)
    existing = count_rostered_own_handcuffs(roster, levels, params)
    count_mult = own_handcuff_count_multiplier(existing, params)
    target = min(
        params.handcuff_max_bonus,
        raw_bonus * league_mult * count_mult,
    )
    adjusted = raw_bonus + params.v5_policy_strength * (target - raw_bonus)

    reason_parts: list[str] = ["direct backup to your RB1"]
    if league_mult < 0.99:
        reason_parts.append(f"discounted in a {settings.team_count}-team league")
    if existing >= 1:
        reason_parts.append("second rostered own handcuff has reduced insurance value")
    reason = (
        ", ".join(reason_parts)
        if params.v5_policy_strength > 0.0 and adjusted >= params.handcuff_min_reason_points
        else None
    )
    return raw_bonus, adjusted, existing, count_mult * league_mult, reason


def optionality_for_player_v5(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    phase: DraftPhase,
    params: V5FormulaParams,
    current_round: int,
) -> V5OptionalityResult:
    upside, upside_reason = late_round_upside(player, phase, params, levels)
    contingent, raw_handcuff, handcuff_reason = contingent_value(
        player, roster, phase, params, levels
    )
    ir_value, ir_reason = ir_stash_value(
        player, roster, settings, current_round, phase, params
    )

    raw_bonus, adjusted_bonus, own_count, count_mult, v5_reason = adjust_handcuff_bonus(
        player, roster, settings, levels, raw_handcuff, params
    )
    league_mult = (
        league_handcuff_multiplier(settings.team_count, params)
        if is_own_handcuff_candidate(player, roster, levels, params)[0]
        else 1.0
    )

    handcuff_component_reason = handcuff_reason if params.v5_policy_strength <= 0.0 else (v5_reason or handcuff_reason)
    components = [
        (upside, upside_reason),
        (adjusted_bonus, handcuff_component_reason),
        (ir_value, ir_reason),
    ]
    if params.optionality_combine == "sum":
        total = sum(value for value, _ in components)
        reason = next((text for value, text in components if text and value > 0), None)
    else:
        best = max(components, key=lambda item: item[0])
        total = best[0]
        reason = best[1] if best[0] > 0 else None

    return V5OptionalityResult(
        late_round_upside=upside,
        contingent_value=contingent,
        handcuff_bonus=adjusted_bonus,
        ir_stash_value=ir_value,
        optionality_value=total,
        reason=reason,
        raw_handcuff_bonus=raw_bonus,
        adjusted_handcuff_bonus=adjusted_bonus,
        own_handcuff_league_multiplier=league_mult,
        own_handcuff_count=own_count,
        own_handcuff_count_multiplier=count_mult,
    )
