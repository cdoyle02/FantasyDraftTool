"""nflverse snap_counts loader helpers for Tier 2 usage filtering."""

from __future__ import annotations

import csv
import gzip
import io
from dataclasses import dataclass

from draft_api.sos.nflverse import normalize_team
from draft_api.workbook.identity import normalize_player_name

SNAP_COUNTS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "snap_counts/snap_counts_{season}.csv.gz"
)

DEFAULT_MIN_OFFENSE_SNAP_PCT = 0.20


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class SnapPctIndex:
    """Lookup offense snap share by team + week + normalized player name."""

    by_key: dict[tuple[str, int, str], float]

    def offense_pct(self, *, team: str, week: int, player_name: str) -> float | None:
        key = (normalize_team(team), week, normalize_player_name(player_name))
        return self.by_key.get(key)


def build_snap_pct_index(
    snap_rows: list[dict[str, str | None]],
    *,
    season: int,
) -> SnapPctIndex:
    by_key: dict[tuple[str, int, str], float] = {}
    for row in snap_rows:
        row_season = _parse_int(row.get("season"))
        if row_season is not None and row_season != season:
            continue
        if (row.get("game_type") or row.get("season_type") or "REG").upper() not in (
            "REG",
            "REGULAR",
        ):
            continue
        week = _parse_int(row.get("week"))
        if week is None:
            continue
        team = normalize_team(row.get("team") or "")
        if not team:
            continue
        name = (row.get("player") or "").strip()
        if not name:
            continue
        pct = _parse_float(row.get("offense_pct"))
        if pct is None:
            continue
        by_key[(team, week, normalize_player_name(name))] = pct
    return SnapPctIndex(by_key=by_key)


def parse_snap_counts_csv(text: str, *, season: int) -> list[dict[str, str | None]]:
    reader = csv.DictReader(io.StringIO(text))
    return [{k: (None if v == "" else v) for k, v in dict(row).items()} for row in reader]


def decode_snap_csv(raw: bytes) -> str:
    try:
        return gzip.decompress(raw).decode("utf-8")
    except OSError:
        return raw.decode("utf-8")
