"""Workbook WR outside vs slot alignment classification."""

from draft_api.workbook.alignment import Alignment, classify_wr_alignment


def test_wr_slot_maps_to_slot():
    assert classify_wr_alignment(position="WR", alignment_raw="slot") == "slot"
    assert classify_wr_alignment(position="WR", alignment_raw="SLOT") == "slot"
    assert classify_wr_alignment(position="WR", alignment_raw="in_slot") == "slot"


def test_non_wr_in_slot_returns_none():
    assert classify_wr_alignment(position="TE", alignment_raw="slot") is None
    assert classify_wr_alignment(position="RB", alignment_raw="slot") is None


def test_wr_outside_labels_map_to_outside():
    assert classify_wr_alignment(position="WR", alignment_raw="wide") == "outside"
    assert classify_wr_alignment(position="WR", alignment_raw="OUTSIDE") == "outside"
    assert classify_wr_alignment(position="WR", alignment_raw="boundary") == "outside"


def test_wr_missing_or_unknown_alignment_is_other():
    assert classify_wr_alignment(position="WR", alignment_raw=None) == "other"
    assert classify_wr_alignment(position="WR", alignment_raw="") == "other"
    assert classify_wr_alignment(position="WR", alignment_raw="backfield") == "other"


def test_alignment_type_literal():
    value: Alignment | None = classify_wr_alignment(position="WR", alignment_raw="wide")
    assert value == "outside"
