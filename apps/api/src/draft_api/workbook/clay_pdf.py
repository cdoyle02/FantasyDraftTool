"""Parse Mike Clay WR/CB cheat sheet layout text (pdftotext -layout)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ClayPos = Literal["L", "S", "R"]

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
