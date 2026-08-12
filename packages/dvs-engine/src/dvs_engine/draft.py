"""Immutable event helpers for snake-draft state."""

from __future__ import annotations

from .models import DraftState, Pick, team_on_clock


class DraftEventError(ValueError):
    """Raised when a draft event violates state invariants."""


def validate_state(state: DraftState) -> None:
    seen: set[str] = set()
    seen_events: set[str] = set()
    for expected_number, pick in enumerate(state.pick_history, start=1):
        if pick.pick_number != expected_number:
            raise DraftEventError(f"expected pick {expected_number}, got {pick.pick_number}")
        expected_team = team_on_clock(expected_number, state.team_count)
        if pick.team_id != expected_team:
            raise DraftEventError(
                f"team {pick.team_id} cannot make pick {expected_number}; "
                f"expected team {expected_team}"
            )
        if pick.player_id in seen:
            raise DraftEventError(f"player {pick.player_id} was drafted more than once")
        if pick.event_id in seen_events:
            raise DraftEventError(f"event {pick.event_id} was replayed more than once")
        seen.add(pick.player_id)
        seen_events.add(pick.event_id)


def apply_pick(
    state: DraftState,
    player_id: str,
    team_id: str | None = None,
    timestamp: str = "",
    event_id: str = "",
) -> DraftState:
    validate_state(state)
    expected_team = state.team_on_clock
    actual_team = team_id or expected_team
    if actual_team != expected_team:
        raise DraftEventError(f"team {actual_team} is not on the clock; expected {expected_team}")
    if any(pick.player_id == player_id for pick in state.pick_history):
        raise DraftEventError(f"player {player_id} has already been drafted")
    pick = Pick(state.current_pick, actual_team, player_id, timestamp, event_id)
    return DraftState(state.team_count, state.pick_history + (pick,))


def undo_last_pick(state: DraftState) -> DraftState:
    validate_state(state)
    if not state.pick_history:
        raise DraftEventError("cannot undo an empty draft")
    return DraftState(state.team_count, state.pick_history[:-1])


def correct_last_pick(state: DraftState, player_id: str) -> DraftState:
    if not state.pick_history:
        raise DraftEventError("cannot correct an empty draft")
    last_pick = state.pick_history[-1]
    prior = undo_last_pick(state)
    return apply_pick(prior, player_id, last_pick.team_id, last_pick.timestamp)
