"""Classify nflverse / FTN target alignment for Workbook WR outside vs slot splits."""

from __future__ import annotations

from typing import Literal

Alignment = Literal["outside", "slot", "other"]

_OUTSIDE_TOKENS = frozenset({"wide", "outside", "boundary"})


def classify_wr_alignment(*, position: str, alignment_raw: str | None) -> Alignment | None:
    """Map a charted alignment string to outside/slot/other for WR targets only.

    Non-WR positions return ``None`` even when charted in the slot (TE/RB excluded).
    ``alignment_raw`` is matched case-insensitively: substring ``slot`` → slot;
    tokens wide/outside/boundary → outside; missing or unknown → other.
    """
    if position != "WR":
        return None
    if alignment_raw is None or alignment_raw == "":
        return "other"
    normalized = alignment_raw.strip().lower()
    if "slot" in normalized:
        return "slot"
    if any(token in normalized for token in _OUTSIDE_TOKENS):
        return "outside"
    return "other"
