"""Draft-phase weighting for the V4.1 late-round optionality layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .lineup import starter_slot_fill
from .models import FormulaParams, LeagueSettings, Player, Position


@dataclass(frozen=True, slots=True)
class DraftPhase:
    progress: float
    starter_completion: float
    late_weight: float
    starter_slots_filled: int
    starter_slots_total: int
    open_starter_slots: tuple[str, ...]


def _smoothstep(value: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if value >= start else 0.0
    if value <= start:
        return 0.0
    if value >= end:
        return 1.0
    t = (value - start) / (end - start)
    return t * t * (3.0 - 2.0 * t)


def draft_phase(
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    params: FormulaParams,
    current_round: int,
    position_caps: Mapping[Position, int] | None = None,
) -> DraftPhase:
    """Compute draft progress and the late-round transition weight."""
    progress = current_round / max(1, settings.rounds)
    fill = starter_slot_fill(roster, settings, levels, position_caps)
    if fill.total <= 0:
        starter_completion = 1.0
    else:
        starter_completion = fill.filled / fill.total
    progress_weight = _smoothstep(
        progress, params.late_phase_start_progress, 1.0
    )
    late_weight = progress_weight * (0.35 + 0.65 * starter_completion)
    return DraftPhase(
        progress=progress,
        starter_completion=starter_completion,
        late_weight=late_weight,
        starter_slots_filled=fill.filled,
        starter_slots_total=fill.total,
        open_starter_slots=fill.open_slots,
    )


def player_fills_open_starter(
    player: Player, open_slots: Sequence[str]
) -> bool:
    """True when the player can occupy an open non-K/DST starter slot."""
    if player.position in (Position.K, Position.DST):
        return False
    if player.position.value in open_slots:
        return True
    if player.position in (Position.RB, Position.WR, Position.TE) and "FLEX" in open_slots:
        return True
    if player.position in (
        Position.QB,
        Position.RB,
        Position.WR,
        Position.TE,
    ) and "SUPERFLEX" in open_slots:
        return True
    return False
