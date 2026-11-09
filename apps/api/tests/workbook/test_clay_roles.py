"""Clay last-known role index and display-name lookup."""

from __future__ import annotations

from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.roles import (
    build_role_index,
    lookup_role,
    merge_last_known,
)


def _wr(name: str, *, slot_pct: int = 50, pos: str = "L") -> ClayWrRow:
    return ClayWrRow(
        team="BUF",
        name=name,
        pos=pos,  # type: ignore[arg-type]
        lwr_pct=20,
        slot_pct=slot_pct,
        rwr_pct=20,
    )


def test_build_role_index_keys_by_normalized_name() -> None:
    rows = [
        _wr("Ja'Marr Chase", slot_pct=10),
        _wr("Khalil Shakir", slot_pct=80),
    ]
    index = build_role_index(rows)
    assert index["jamarr chase"] == "outside"
    assert index["khalil shakir"] == "slot"


def test_merge_last_known_keeps_previous_when_missing_from_current() -> None:
    previous = {"bye week guy": "slot", "still here": "outside"}
    current = {"still here": "slot", "new guy": "outside"}
    merged = merge_last_known(current, previous)
    assert merged == {
        "bye week guy": "slot",
        "still here": "slot",
        "new guy": "outside",
    }


def test_merge_last_known_accepts_none_previous() -> None:
    current = {"a": "slot"}
    assert merge_last_known(current, None) == {"a": "slot"}


def test_lookup_role_normalizes_display_name() -> None:
    index = {"jamarr chase": "outside", "khalil shakir": "slot"}
    assert lookup_role(index, "Ja'Marr Chase") == "outside"
    assert lookup_role(index, "Khalil Shakir") == "slot"
    assert lookup_role(index, "Unknown WR") is None
