"""Clay WR/CB cheat sheet layout parse and role classification."""

from __future__ import annotations

from pathlib import Path

import pytest
from draft_api.workbook.clay_pdf import (
    CLAY_PDF_URL_TEMPLATE,
    ClayPdfError,
    ClayWrRow,
    extract_layout_text_from_pdf,
    fetch_clay_pdf_bytes,
    load_clay_wr_rows,
    parse_clay_layout_text,
)
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


def test_fetch_clay_pdf_bytes_uses_season_suffix() -> None:
    calls: list[str] = []

    def fake_get(url: str) -> bytes:
        calls.append(url)
        return b"%PDF-test"

    assert fetch_clay_pdf_bytes(2026, http_get=fake_get) == b"%PDF-test"
    assert calls == [CLAY_PDF_URL_TEMPLATE.format(yy=26)]


def test_fetch_clay_pdf_bytes_wraps_failures() -> None:
    def boom(_url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(ClayPdfError, match="failed to fetch"):
        fetch_clay_pdf_bytes(2026, http_get=boom)


def test_extract_layout_text_from_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def __init__(self, text: str | None) -> None:
            self.text = text

        def extract_text(self, extraction_mode: str = "plain") -> str | None:
            assert extraction_mode == "layout"
            return self.text

    class FakeReader:
        def __init__(self, stream: object) -> None:
            self.pages = [FakePage("first page"), FakePage(None), FakePage("second page")]

    monkeypatch.setattr("draft_api.workbook.clay_pdf.PdfReader", FakeReader)

    assert extract_layout_text_from_pdf(b"%PDF-test") == "first page\nsecond page"


def test_extract_layout_text_from_pdf_wraps_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenReader:
        def __init__(self, stream: object) -> None:
            raise ValueError("bad pdf")

    monkeypatch.setattr("draft_api.workbook.clay_pdf.PdfReader", BrokenReader)

    with pytest.raises(ClayPdfError, match="failed to extract"):
        extract_layout_text_from_pdf(b"not a pdf")


def test_load_clay_wr_rows_fetches_extracts_and_parses(
    monkeypatch: pytest.MonkeyPatch, layout_text: str
) -> None:
    def fake_get(_url: str) -> bytes:
        return b"%PDF-test"

    monkeypatch.setattr(
        "draft_api.workbook.clay_pdf.extract_layout_text_from_pdf", lambda data: layout_text
    )

    rows = load_clay_wr_rows(2026, http_get=fake_get)

    assert any(row.name == "Khalil Shakir" for row in rows)


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
