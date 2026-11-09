"""Clay WR role classification and name/team normalization for Workbook."""

from __future__ import annotations

from typing import Literal

from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.identity import normalize_player_name, normalize_team

ClayRole = Literal["slot", "outside"]
Role = ClayRole

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


def build_role_index(rows: list[ClayWrRow]) -> dict[str, Role]:
    """Map normalized player name to Clay slot/outside role."""
    return {normalize_player_name(row.name): classify_clay_role(row) for row in rows}


def merge_last_known(
    current: dict[str, Role],
    previous: dict[str, Role] | None,
) -> dict[str, Role]:
    """Current week wins; retain previous roles for players absent this week."""
    merged = dict(previous or ())
    merged.update(current)
    return merged


def lookup_role(index: dict[str, Role], player_display_name: str) -> Role | None:
    """Resolve role for an ESPN/display name via the normalized index key."""
    return index.get(normalize_player_name(player_display_name))
