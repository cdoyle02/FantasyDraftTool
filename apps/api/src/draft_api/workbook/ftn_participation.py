"""FTN Participation play-level Out/Slot — fixture dual-run only until gates pass.

No live FTN client, credentials, or network path lives here. CI and local tests
feed redacted sample CSVs under ``tests/workbook/fixtures/``.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from draft_api.workbook.alignment import Alignment, classify_wr_alignment
from draft_api.workbook.fantasy import receiving_points
from draft_api.workbook.identity import normalize_team
from draft_api.workbook.nflverse import PositionalWeekRate

AlignmentSource = Literal["ftn_participation", "clay_role", "none"]

# Locked coding dictionary (gate 4) — WR-only Slot; TE/RB excluded via classify.
SKP_POS_TO_ALIGNMENT: dict[str, str] = {
    "SLT": "slot",
    "SLOT": "slot",
    "WR": "wide",
    "LWR": "wide",
    "RWR": "wide",
    "OUT": "wide",
    "BOUNDARY": "wide",
}
SKP_POS_EXCLUDED = frozenset({"Y-TE", "H-TE", "HB", "FB", "TE", "RB"})


@dataclass(frozen=True, slots=True)
class FtnParticipationEvent:
    """One redacted Participation target aligned to nflverse ids when present."""

    nflverse_game_id: str
    play_id: str
    week: int
    posteam: str
    defteam: str
    receiver_player_id: str
    receiver_position: str
    skp_pos: str
    targets: float = 1.0
    receptions: float = 0.0
    rec_yards: float = 0.0
    rec_tds: float = 0.0


def map_skp_pos(skp_pos: str) -> Alignment | None:
    """Map FTN ``skp_pos`` to Workbook alignment; non-WR charted values → None."""
    token = (skp_pos or "").strip().upper()
    if not token or token in SKP_POS_EXCLUDED:
        return None
    raw = SKP_POS_TO_ALIGNMENT.get(token)
    if raw is None:
        return "other"
    # classify_wr_alignment still enforces WR-only when position is passed.
    return classify_wr_alignment(position="WR", alignment_raw=raw)


def parse_ftn_participation_csv(text: str, *, season: int) -> list[FtnParticipationEvent]:
    """Parse a redacted Participation sample (never live credentials)."""
    reader = csv.DictReader(io.StringIO(text))
    required = (
        "nflverse_game_id",
        "play_id",
        "week",
        "posteam",
        "defteam",
        "receiver_player_id",
        "receiver_position",
        "skp_pos",
    )
    if not reader.fieldnames:
        return []
    missing = [name for name in required if name not in reader.fieldnames]
    if missing:
        raise ValueError(f"ftn participation fixture missing columns: {', '.join(missing)}")

    events: list[FtnParticipationEvent] = []
    for row in reader:
        week_raw = row.get("week") or ""
        try:
            week = int(float(week_raw))
        except ValueError:
            continue
        if week < 1 or week > 18:
            continue
        # Optional season filter when the fixture includes a season column.
        if "season" in (reader.fieldnames or []):
            try:
                row_season = int(float(row.get("season") or ""))
            except ValueError:
                row_season = season
            if row_season != season:
                continue
        events.append(
            FtnParticipationEvent(
                nflverse_game_id=str(row.get("nflverse_game_id") or "").strip(),
                play_id=str(row.get("play_id") or "").strip(),
                week=week,
                posteam=normalize_team(row.get("posteam") or ""),
                defteam=normalize_team(row.get("defteam") or ""),
                receiver_player_id=str(row.get("receiver_player_id") or "").strip(),
                receiver_position=str(row.get("receiver_position") or "").strip().upper(),
                skp_pos=str(row.get("skp_pos") or "").strip(),
                targets=_float_or(row.get("targets"), 1.0),
                receptions=_float_or(row.get("receptions"), 0.0),
                rec_yards=_float_or(row.get("rec_yards"), 0.0),
                rec_tds=_float_or(row.get("rec_tds"), 0.0),
            )
        )
    return events


def _float_or(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _empty_sums() -> dict[str, float]:
    return {
        "targets": 0.0,
        "receptions": 0.0,
        "rec_yards": 0.0,
        "rec_tds": 0.0,
        "fantasy_points": 0.0,
    }


def aggregate_out_slot_from_ftn(
    events: list[FtnParticipationEvent],
) -> tuple[
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
]:
    """Build out_wr / slot_wr OFF+DEF bags from play-level Participation events.

    TE/RB charted in slot are dropped (WR-only Slot rule).
    """
    out_wr_off: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_sums)
    out_wr_def: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_sums)
    slot_wr_off: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_sums)
    slot_wr_def: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_sums)

    for event in events:
        if not event.posteam or not event.defteam:
            continue
        token = event.skp_pos.strip().upper()
        if token in SKP_POS_EXCLUDED:
            continue
        # Non-WR positions never contribute to Out/Slot WR bags.
        if event.receiver_position != "WR":
            continue
        mapped = SKP_POS_TO_ALIGNMENT.get(token)
        alignment = classify_wr_alignment(
            position="WR",
            alignment_raw=mapped,
        )
        if alignment not in ("slot", "outside"):
            continue

        fp = receiving_points(
            receptions=event.receptions,
            yards=event.rec_yards,
            tds=event.rec_tds,
            scoring="ppr",
        )
        bag = {
            "targets": event.targets,
            "receptions": event.receptions,
            "rec_yards": event.rec_yards,
            "rec_tds": event.rec_tds,
            "fantasy_points": fp,
        }
        off = slot_wr_off if alignment == "slot" else out_wr_off
        deff = slot_wr_def if alignment == "slot" else out_wr_def
        off_key = (event.posteam, event.week)
        def_key = (event.defteam, event.week)
        for field, value in bag.items():
            off[off_key][field] += value
            deff[def_key][field] += value

    def _finalize(
        sums: dict[tuple[str, int], dict[str, float]],
    ) -> dict[tuple[str, int], PositionalWeekRate]:
        return {
            key: PositionalWeekRate(
                targets=bag["targets"],
                receptions=bag["receptions"],
                rec_yards=bag["rec_yards"],
                rec_tds=bag["rec_tds"],
                fantasy_points=bag["fantasy_points"],
            )
            for key, bag in sums.items()
        }

    positional_off = {
        "out_wr": _finalize(out_wr_off),
        "slot_wr": _finalize(slot_wr_off),
    }
    positional_def = {
        "out_wr": _finalize(out_wr_def),
        "slot_wr": _finalize(slot_wr_def),
    }
    return positional_off, positional_def


def _has_out_slot_rates(
    bags: dict[str, dict[tuple[str, int], PositionalWeekRate]],
) -> bool:
    return bool(bags.get("out_wr") or bags.get("slot_wr"))


def prefer_out_slot_alignment(
    *,
    clay_off: dict[str, dict[tuple[str, int], PositionalWeekRate]],
    clay_def: dict[str, dict[tuple[str, int], PositionalWeekRate]],
    ftn_off: dict[str, dict[tuple[str, int], PositionalWeekRate]] | None = None,
    ftn_def: dict[str, dict[tuple[str, int], PositionalWeekRate]] | None = None,
) -> tuple[
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
    AlignmentSource,
]:
    """Dual-run: FTN wins when present; else Clay roles; else empty + ``none``."""
    if ftn_off is not None and ftn_def is not None and (
        _has_out_slot_rates(ftn_off) or _has_out_slot_rates(ftn_def)
    ):
        return ftn_off, ftn_def, "ftn_participation"
    if _has_out_slot_rates(clay_off) or _has_out_slot_rates(clay_def):
        return clay_off, clay_def, "clay_role"
    return (
        {"out_wr": {}, "slot_wr": {}},
        {"out_wr": {}, "slot_wr": {}},
        "none",
    )


def alignment_label(source: AlignmentSource) -> str:
    if source == "ftn_participation":
        return "Out/Slot (play-level)"
    if source == "clay_role":
        return "Out/Slot (Clay role)"
    return "Out/Slot (unavailable)"
