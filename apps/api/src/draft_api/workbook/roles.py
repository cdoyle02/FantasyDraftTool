"""Clay WR role classification and name/team normalization for Workbook."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.identity import normalize_team

ClayRole = Literal["slot", "outside"]

SLOT_PCT_THRESHOLD = 45

# Clay PDF uses legacy abbreviations before our nflverse alias map.
CLAY_TEAM_ALIASES: dict[str, str] = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
}


def normalize_clay_team(team: str) -> str:
    """Map Clay team codes, then apply shared workbook team normalization."""
    raw = team.strip().upper()
    mapped = CLAY_TEAM_ALIASES.get(raw, raw)
    return normalize_team(mapped)


def classify_clay_role(row: ClayWrRow) -> ClayRole:
    """Slot-primary if Slot% is high enough, else Clay Pos=S, else outside."""
    if row.slot_pct >= SLOT_PCT_THRESHOLD:
        return "slot"
    if row.pos == "S":
        return "slot"
    return "outside"


def normalize_player_name(name: str) -> str:
    """Lowercase join key: strip accents, punctuation, and suffixes."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", text)
    return re.sub(r"\s+", " ", text).strip()
