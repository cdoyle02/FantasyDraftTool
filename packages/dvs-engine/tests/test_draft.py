import pytest

from dvs_engine import (
    DraftEventError,
    DraftState,
    Pick,
    apply_pick,
    correct_last_pick,
    team_on_clock,
    undo_last_pick,
    validate_state,
)


def test_snake_team_on_clock():
    assert [team_on_clock(pick, 4) for pick in range(1, 13)] == [
        "1", "2", "3", "4", "4", "3", "2", "1", "1", "2", "3", "4"
    ]


def test_apply_pick_builds_immutable_history_and_rosters(empty_state):
    after_one = apply_pick(
        empty_state,
        "p1",
        timestamp="2026-08-12T12:00:00Z",
        event_id="event-1",
    )
    after_two = apply_pick(after_one, "p2")

    assert empty_state.pick_history == ()
    assert after_one.pick_history[0].timestamp == "2026-08-12T12:00:00Z"
    assert after_one.pick_history[0].event_id == "event-1"
    assert after_two.current_pick == 3
    assert after_two.rosters["1"] == ("p1",)
    assert after_two.rosters["2"] == ("p2",)


def test_apply_rejects_wrong_team_and_duplicate(empty_state):
    with pytest.raises(DraftEventError, match="not on the clock"):
        apply_pick(empty_state, "p1", "2")

    state = apply_pick(empty_state, "p1")
    with pytest.raises(DraftEventError, match="already been drafted"):
        apply_pick(state, "p1")


def test_undo_and_correction(empty_state):
    state = apply_pick(apply_pick(empty_state, "p1"), "p2")
    undone = undo_last_pick(state)
    corrected = correct_last_pick(state, "replacement")

    assert undone.current_pick == 2
    assert corrected.pick_history[-1].player_id == "replacement"
    assert corrected.pick_history[-1].team_id == "2"


def test_validation_rejects_gaps_and_wrong_snake_team():
    gap = DraftState(4, (Pick(2, "1", "p1"),))
    wrong_team = DraftState(4, (Pick(1, "2", "p1"),))

    with pytest.raises(DraftEventError, match="expected pick 1"):
        validate_state(gap)
    with pytest.raises(DraftEventError, match="expected team 1"):
        validate_state(wrong_team)


def test_cannot_undo_empty_draft(empty_state):
    with pytest.raises(DraftEventError, match="empty"):
        undo_last_pick(empty_state)
