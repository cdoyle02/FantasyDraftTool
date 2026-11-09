"""FTN Participation fixture dual-run (no live FTN client)."""

from __future__ import annotations

from pathlib import Path

from draft_api.workbook.ftn_participation import (
    aggregate_out_slot_from_ftn,
    alignment_label,
    parse_ftn_participation_csv,
    prefer_out_slot_alignment,
)
from draft_api.workbook.nflverse import PositionalWeekRate

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SEASON = 2026


def test_parse_ftn_participation_fixture() -> None:
    text = (FIXTURES / "ftn_participation_redacted.csv").read_text(encoding="utf-8")
    events = parse_ftn_participation_csv(text, season=SEASON)
    assert len(events) == 5
    assert events[1].skp_pos == "SLT"


def test_aggregate_ftn_wr_only_slot_excludes_te_rb() -> None:
    text = (FIXTURES / "ftn_participation_redacted.csv").read_text(encoding="utf-8")
    events = parse_ftn_participation_csv(text, season=SEASON)
    off, deff = aggregate_out_slot_from_ftn(events)

    slot_aaa = off["slot_wr"][("AAA", 5)]
    # Only WR_SLOT_1 counts — TE/RB SLT rows dropped.
    assert slot_aaa.targets == 1.0
    assert slot_aaa.receptions == 1.0
    assert slot_aaa.rec_yards == 8.0
    assert slot_aaa.rec_tds == 1.0

    out_aaa = off["out_wr"][("AAA", 5)]
    assert out_aaa.targets == 1.0
    out_bbb = off["out_wr"][("BBB", 5)]
    assert out_bbb.targets == 1.0

    # DEF allowed against AAA includes BBB's outside WR target.
    assert deff["out_wr"][("AAA", 5)].targets == 1.0


def test_prefer_ftn_when_present_else_clay() -> None:
    text = (FIXTURES / "ftn_participation_redacted.csv").read_text(encoding="utf-8")
    ftn_off, ftn_def = aggregate_out_slot_from_ftn(
        parse_ftn_participation_csv(text, season=SEASON)
    )
    clay_off = {
        "out_wr": {("AAA", 5): PositionalWeekRate(targets=9, fantasy_points=20)},
        "slot_wr": {},
    }
    clay_def = {"out_wr": {}, "slot_wr": {}}

    off, _deff, source = prefer_out_slot_alignment(
        clay_off=clay_off, clay_def=clay_def, ftn_off=ftn_off, ftn_def=ftn_def
    )
    assert source == "ftn_participation"
    assert alignment_label(source) == "Out/Slot (play-level)"
    assert off["slot_wr"][("AAA", 5)].targets == 1.0

    off2, _d2, source2 = prefer_out_slot_alignment(
        clay_off=clay_off, clay_def=clay_def, ftn_off=None, ftn_def=None
    )
    assert source2 == "clay_role"
    assert alignment_label(source2) == "Out/Slot (Clay role)"
    assert off2["out_wr"][("AAA", 5)].targets == 9.0

    empty_off, empty_def, source3 = prefer_out_slot_alignment(
        clay_off={"out_wr": {}, "slot_wr": {}},
        clay_def={"out_wr": {}, "slot_wr": {}},
    )
    assert source3 == "none"
    assert empty_off["out_wr"] == {}
    assert empty_def["slot_wr"] == {}
