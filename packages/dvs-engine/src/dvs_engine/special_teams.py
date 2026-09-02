"""K/DST eligibility gates for the V4.1 decision engine."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .models import FormulaParams, LeagueSettings, Player, Position


@dataclass(frozen=True, slots=True)
class SpecialTeamsStatus:
    eligible: bool
    cap_blocked: bool
    timing_blocked: bool
    timing_penalty: float


def _special_teams_slots(settings: LeagueSettings) -> dict[Position, int]:
    slots = settings.roster_slots
    return {
        Position.K: int(slots.get("K", 0)),
        Position.DST: int(slots.get("DST", 0)),
    }


def _unfilled_special_teams_slots(
    roster: Sequence[Player], settings: LeagueSettings
) -> int:
    counts = Counter(player.position for player in roster)
    required = _special_teams_slots(settings)
    return sum(
        max(0, required[position] - counts[position])
        for position in (Position.K, Position.DST)
    )


def _timing_window_rounds(position: Position, params: FormulaParams) -> int:
    if position == Position.K:
        return params.kicker_final_rounds
    return params.dst_final_rounds


def special_teams_status(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    params: FormulaParams,
) -> SpecialTeamsStatus:
    """Return eligibility and timing penalty for K/DST players."""
    if player.position not in (Position.K, Position.DST):
        return SpecialTeamsStatus(
            eligible=True,
            cap_blocked=False,
            timing_blocked=False,
            timing_penalty=0.0,
        )

    counts = Counter(item.position for item in roster)
    required = _special_teams_slots(settings)[player.position]
    cap_blocked = required > 0 and counts[player.position] >= required

    remaining_rounds = max(0, settings.rounds - current_round + 1)
    unfilled = _unfilled_special_teams_slots(roster, settings)
    safety_valve = unfilled > 0 and remaining_rounds <= unfilled

    window = _timing_window_rounds(player.position, params)
    timing_blocked = current_round <= settings.rounds - window and not safety_valve

    eligible = not cap_blocked and not timing_blocked
    timing_penalty = 0.0
    if timing_blocked and not params.special_teams_hard_gate:
        timing_penalty = -settings.guardrail_weight * params.special_teams_timing_penalty_multiple

    return SpecialTeamsStatus(
        eligible=eligible,
        cap_blocked=cap_blocked,
        timing_blocked=timing_blocked,
        timing_penalty=timing_penalty,
    )


def is_special_teams_eligible(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    params: FormulaParams,
) -> bool:
    """True when a K/DST player may be drafted or counted in lookahead."""
    if player.position not in (Position.K, Position.DST):
        return True
    if params.special_teams_hard_gate:
        return special_teams_status(
            player, roster, settings, current_round, params
        ).eligible
    return not special_teams_status(
        player, roster, settings, current_round, params
    ).cap_blocked


def future_special_teams_eligible(
    player: Player,
    roster_plus_candidate: Sequence[Player],
    settings: LeagueSettings,
    next_round: int,
    params: FormulaParams,
) -> bool:
    """Candidate-conditioned future K/DST eligibility for lookahead."""
    mode = params.special_teams_lookahead_mode
    if player.position not in (Position.K, Position.DST):
        return True
    if mode == "never":
        return False
    if mode == "always":
        return True
    return is_special_teams_eligible(
        player, roster_plus_candidate, settings, next_round, params
    )


def opponent_at_special_teams_cap(
    roster: Sequence[Player],
    position: Position,
    settings: LeagueSettings,
) -> bool:
    """True when an opponent roster is at the K/DST slot cap."""
    if position not in (Position.K, Position.DST):
        return False
    required = _special_teams_slots(settings).get(position, 0)
    if required <= 0:
        return False
    counts = Counter(item.position for item in roster)
    return counts[position] >= required
