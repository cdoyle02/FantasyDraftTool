"""Parse Mike Clay WR/CB cheat sheet layout text (pdftotext -layout)."""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from pypdf import PdfReader

ClayPos = Literal["L", "S", "R"]

CLAY_PDF_URL_TEMPLATE = "https://g.espncdn.com/s/ffldraftkit/{yy}/NFL{yy}_CS_WRCB.pdf"

# Receiver table rows: team, name, L/S/R, proj tgt%, ht, wt, LWR%, Slot%, RWR%.
_RECEIVER_ROW = re.compile(
    r"^\s*([A-Z]{2,3})\s+"
    r"(.+?)\s+"
    r"([LSR])\s+"
    r"\d+%\s+"
    r"\d+-\d+\s+"
    r"\d+\s+"
    r"(\d+)%\s+"
    r"(\d+)%\s+"
    r"(\d+)%",
)


@dataclass(frozen=True, slots=True)
class ClayWrRow:
    team: str
    name: str
    pos: ClayPos
    lwr_pct: int
    slot_pct: int
    rwr_pct: int


class ClayPdfError(RuntimeError):
    """Raised when Clay PDF download or text extraction fails."""


def _default_http_get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read()


def fetch_clay_pdf_bytes(
    season: int, *, http_get: Callable[[str], bytes] | None = None
) -> bytes:
    """Download Mike Clay's WR/CB cheat sheet PDF for a season."""
    yy = season % 100
    url = CLAY_PDF_URL_TEMPLATE.format(yy=yy)
    getter = http_get or _default_http_get
    try:
        data = getter(url)
    except Exception as exc:  # noqa: BLE001 - normalize caller/network errors for API use.
        raise ClayPdfError(f"failed to fetch Clay PDF: {url}") from exc
    if not data:
        raise ClayPdfError(f"failed to fetch Clay PDF: empty response from {url}")
    return data


def extract_layout_text_from_pdf(data: bytes) -> str:
    """Extract layout-preserving text from a Clay PDF payload."""
    try:
        reader = PdfReader(BytesIO(data))
        pages = [
            text
            for page in reader.pages
            if (text := page.extract_text(extraction_mode="layout"))
        ]
    except Exception as exc:  # noqa: BLE001 - pypdf raises several parser-specific errors.
        raise ClayPdfError("failed to extract text from Clay PDF") from exc
    return "\n".join(pages)


def load_clay_wr_rows(
    season: int, *, http_get: Callable[[str], bytes] | None = None
) -> list[ClayWrRow]:
    """Fetch, extract, and parse Mike Clay WR alignment rows."""
    data = fetch_clay_pdf_bytes(season, http_get=http_get)
    text = extract_layout_text_from_pdf(data)
    return parse_clay_layout_text(text)


def parse_clay_layout_text(text: str) -> list[ClayWrRow]:
    """Extract WR alignment rows from Clay cheat-sheet layout text."""
    rows: list[ClayWrRow] = []
    for line in text.splitlines():
        match = _RECEIVER_ROW.match(line)
        if not match:
            continue
        team, name, pos, lwr, slot, rwr = match.groups()
        rows.append(
            ClayWrRow(
                team=team.strip(),
                name=" ".join(name.split()),
                pos=pos,  # type: ignore[arg-type]
                lwr_pct=int(lwr),
                slot_pct=int(slot),
                rwr_pct=int(rwr),
            )
        )
    return rows
