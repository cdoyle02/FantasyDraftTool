"""Clay WR/CB cheat sheet layout parse and role classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from draft_api.workbook.clay_pdf import ClayWrRow, parse_clay_layout_text
from draft_api.workbook.roles import (
    classify_clay_role,
    normalize_clay_team,
    normalize_player_name,
)

FIXTURE = Path(__file__).parent / "fixtures" / "clay_wrcb_week9_layout.txt"


@pytest.fixture
def layout_text() -> str:
    return FIXTURE.read_text()


def _row_by_name(text: str, name_substr: str) -> ClayWrRow:
    for row in parse_clay_layout_text(text):
        if name_substr.lower() in row.name.lower():
            return row
    raise KeyError(name_substr)


@pytest.mark.parametrize(
    ("clay", "expected"),
    [
        ("ARZ", "ARI"),
        ("BLT", "BAL"),
        ("CLV", "CLE"),
        ("HST", "HOU"),
    ],
)
def test_normalize_clay_team_aliases(clay: str, expected: str) -> None:
    assert normalize_clay_team(clay) == expected


def test_parse_returns_multiple_wr_rows(layout_text: str) -> None:
    rows = parse_clay_layout_text(layout_text)
    names = {r.name for r in rows}
    assert "Khalil Shakir" in names
    assert "Ja'Marr Chase" in names
    assert len(rows) >= 7


def test_shakir_classifies_slot(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Shakir")
    assert row.slot_pct == 61
    assert classify_clay_role(row) == "slot"


def test_downs_classifies_slot(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Downs")
    assert classify_clay_role(row) == "slot"


def test_chase_classifies_outside(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Chase")
    assert row.slot_pct == 26
    assert classify_clay_role(row) == "outside"


def test_franklin_pos_s_slot_43_is_slot(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Franklin")
    assert row.pos == "S"
    assert row.slot_pct == 43
    assert classify_clay_role(row) == "slot"


def test_metchie_slot_51_is_slot(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Metchie")
    assert row.pos == "R"
    assert row.slot_pct == 51
    assert classify_clay_role(row) == "slot"


def test_pickens_classifies_outside(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Pickens")
    assert classify_clay_role(row) == "outside"


def test_flowers_classifies_slot(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Flowers")
    assert classify_clay_role(row) == "slot"


def test_normalize_clay_team_on_parsed_row(layout_text: str) -> None:
    row = _row_by_name(layout_text, "Wilson")
    assert row.team == "ARZ"
    assert normalize_clay_team(row.team) == "ARI"


def test_normalize_player_name_strips_punctuation() -> None:
    assert normalize_player_name("Ja'Marr Chase") == "jamarr chase"
    assert normalize_player_name("John Metchie III") == "john metchie"
