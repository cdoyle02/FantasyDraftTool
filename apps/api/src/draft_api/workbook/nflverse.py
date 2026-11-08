"""Download and normalize nflverse PBP + weekly stats + schedules for the Workbook.

Column names below were verified against the live nflverse-data GitHub release
assets and the nflreadr data dictionaries on 2026-11-08 (see each constant's
docstring/comment for the specific source). Where real public data does not
yet cover a field the Workbook spec wants (WR outside/slot alignment), that
gap is called out explicitly rather than guessed at — see "Alignment data"
below and in ``workbook/README.md``.
"""

from __future__ import annotations

import csv
import gzip
import io
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from draft_api.sos.calculate import WEEKS
from draft_api.sos.nflverse import SCHEDULES_URL, STATS_URL, parse_schedule_csv
from draft_api.workbook.alignment import classify_wr_alignment
from draft_api.workbook.calculate import DriveOutcome, PassPlay, TeamRateSlice
from draft_api.workbook.fantasy import receiving_points
from draft_api.workbook.identity import NFL_TEAMS, normalize_team

HttpGetter = Callable[[str], bytes]

# Confirmed via `GET /repos/nflverse/nflverse-data/releases/tags/pbp` asset
# listing (2026-11-08): `play_by_play_{season}.csv.gz` exists for every
# season including the current one.
PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "pbp/play_by_play_{season}.csv.gz"
)

# Confirmed via `GET /repos/nflverse/nflverse-data/releases/tags/ftn_charting`
# asset listing (2026-11-08): this release ships **plain** `.csv` only (no
# `.csv.gz` variant), unlike `pbp`/`stats_player`.
FTN_CHARTING_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "ftn_charting/ftn_charting_{season}.csv"
)

# --- Alignment data (documented assumption) -------------------------------
# The public nflverse `ftn_charting` CSV does **not** include a per-target
# slot/outside alignment column. Verified 2026-11-08 against the official
# dictionary (https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html)
# and a live download of `ftn_charting_2025.csv`: its 29 columns cover play
# context (motion, play-action, screen, blitzers, ...) but no receiver
# alignment. FTN's "Participation Feed" *does* chart per-skill-player
# alignment (`skp_pos` values like WR / SLT / Y-TE / H-TE / HB / FB) per
# https://ftnfantasy.com/ftn-data-nfl-catalog, but that feed is not published
# via nflverse's public release.
#
# Rather than fabricate alignment data, `parse_alignment_csv` looks for
# `ALIGNMENT_COLUMN` defensively: if a future nflverse release (or a
# household-maintained supplemental CSV keyed the same way as FTN charting —
# `nflverse_game_id` + `nflverse_play_id`) adds it, the join activates with
# no code change. Until then the column is absent, `parse_alignment_csv`
# returns an empty mapping, and Out/Slot WR naturally end up with zero
# samples — which the Workbook service layer (Task 7) is specced to render
# as `null` + `insufficient_alignment_sample` rather than guessing.
ALIGNMENT_COLUMN = "receiver_alignment"

USER_AGENT = (
    "Mozilla/5.0 (compatible; FantasyDraftTool/1.0; "
    "+https://github.com/nflverse/nflverse-data)"
)

PositionalGroup = Literal["qb", "all_wr", "out_wr", "slot_wr", "te", "rb"]

# nflverse `stats_player_week` `position` -> Workbook positional group.
# Out/Slot WR are derived separately from PBP + alignment, not from this map.
_STAT_POSITION_GROUPS: dict[str, PositionalGroup] = {
    "QB": "qb",
    "WR": "all_wr",
    "TE": "te",
    "RB": "rb",
}

_RATE_FIELDS: tuple[str, ...] = (
    "targets",
    "receptions",
    "rec_yards",
    "rec_tds",
    "rush_att",
    "rush_yards",
    "rush_tds",
    "pass_yards",
    "pass_tds",
    "fantasy_points",
)

# Required CSV headers (verified against live nflverse assets 2026-11-08).
_STATS_REQUIRED_HEADERS: tuple[str, ...] = (
    "season",
    "season_type",
    "week",
    "player_id",
    "position",
    "team",
    "opponent_team",
    "targets",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "passing_yards",
    "passing_tds",
    "fantasy_points_ppr",
)
_PBP_REQUIRED_HEADERS: tuple[str, ...] = (
    "season",
    "season_type",
    "week",
    "game_id",
    "play_id",
    "posteam",
    "defteam",
    "drive",
    "qb_kneel",
    "pass_attempt",
    "rush_attempt",
    "yards_gained",
    "epa",
    "xpass",
    "series_success",
    "touchdown",
    "complete_pass",
    "receiver_player_id",
)
_SCHEDULE_REQUIRED_HEADERS: tuple[str, ...] = (
    "season",
    "game_type",
    "week",
    "away_team",
    "home_team",
)


class WorkbookNflverseError(RuntimeError):
    """Raised when Workbook nflverse downloads or parsing fail."""


@dataclass(frozen=True, slots=True)
class PositionalWeekRate:
    """One team-week positional OFF (produced) or DEF (allowed) rate bag."""

    targets: float | None = None
    receptions: float | None = None
    rec_yards: float | None = None
    rec_tds: float | None = None
    rush_att: float | None = None
    rush_yards: float | None = None
    rush_tds: float | None = None
    pass_yards: float | None = None
    pass_tds: float | None = None
    fantasy_points: float | None = None


@dataclass(frozen=True, slots=True)
class WorkbookDataset:
    """Normalized season data ready for the Workbook calculators."""

    season: int
    fetched_at: str
    teams: list[str]
    schedule: dict[int, dict[str, str | None]]
    drives: list[DriveOutcome]
    pass_plays: list[PassPlay]
    team_env_off: list[TeamRateSlice]
    team_env_def: list[TeamRateSlice]
    positional_off: dict[str, dict[tuple[str, int], PositionalWeekRate]]
    positional_def: dict[str, dict[tuple[str, int], PositionalWeekRate]]


def default_http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise WorkbookNflverseError(f"nflverse HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise WorkbookNflverseError(
            f"nflverse network error for {url}: {exc.reason}"
        ) from exc


def _decode_csv_bytes(raw: bytes) -> str:
    try:
        return gzip.decompress(raw).decode("utf-8")
    except OSError:
        return raw.decode("utf-8")


def _ensure_csv_headers(
    fieldnames: list[str] | None,
    required: tuple[str, ...],
    *,
    source: str,
) -> None:
    if not fieldnames:
        raise WorkbookNflverseError(f"{source}: missing CSV header row")
    missing = [name for name in required if name not in fieldnames]
    if missing:
        joined = ", ".join(missing)
        raise WorkbookNflverseError(f"{source}: missing required columns: {joined}")


def _parse_float(value: str | None, *, field: str) -> float:
    """Parse a stat counter; empty cells mean zero when the column exists."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError as exc:
        raise WorkbookNflverseError(
            f"invalid numeric value for {field}: {value!r}"
        ) from exc


def _parse_optional_float(value: str | None, *, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise WorkbookNflverseError(
            f"invalid numeric value for {field}: {value!r}"
        ) from exc


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool:
    """Accept nflverse's `0`/`1` PBP convention and FTN's `TRUE`/`FALSE`."""
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in ("1", "true", "t", "yes")


def _empty_rate_sums() -> dict[str, float]:
    return dict.fromkeys(_RATE_FIELDS, 0.0)


def parse_positional_stats(
    text: str, *, season: int
) -> tuple[
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
    dict[str, str],
]:
    """Aggregate QB/ALL WR/TE/RB OFF-produced and DEF-allowed rates by team-week.

    Also returns a `player_id -> position` map built from the same rows, used
    by `parse_play_by_play` to resolve a PBP target's position for Out/Slot
    WR classification without needing a separate roster join.
    """
    reader = csv.DictReader(io.StringIO(text))
    _ensure_csv_headers(
        reader.fieldnames, _STATS_REQUIRED_HEADERS, source="stats_player_week"
    )
    player_position: dict[str, str] = {}
    off_sums: dict[tuple[str, str, int], dict[str, float]] = defaultdict(_empty_rate_sums)
    def_sums: dict[tuple[str, str, int], dict[str, float]] = defaultdict(_empty_rate_sums)

    for row in reader:
        row_season = _parse_int(row.get("season", ""))
        if row_season is not None and row_season != season:
            continue
        if (row.get("season_type") or "").upper() not in ("REG", "REGULAR"):
            continue
        week = _parse_int(row.get("week", ""))
        if week is None or week < 1 or week > 18:
            continue

        position = (row.get("position") or "").upper()
        player_id = row.get("player_id") or ""
        if player_id:
            player_position[player_id] = position

        group = _STAT_POSITION_GROUPS.get(position)
        if group is None:
            continue
        team = normalize_team(row.get("team") or "")
        opponent = normalize_team(row.get("opponent_team") or "")
        if not team or not opponent:
            continue

        bag = {
            "targets": _parse_float(row.get("targets"), field="targets"),
            "receptions": _parse_float(row.get("receptions"), field="receptions"),
            "rec_yards": _parse_float(row.get("receiving_yards"), field="receiving_yards"),
            "rec_tds": _parse_float(row.get("receiving_tds"), field="receiving_tds"),
            "rush_att": _parse_float(row.get("carries"), field="carries"),
            "rush_yards": _parse_float(row.get("rushing_yards"), field="rushing_yards"),
            "rush_tds": _parse_float(row.get("rushing_tds"), field="rushing_tds"),
            "pass_yards": _parse_float(row.get("passing_yards"), field="passing_yards"),
            "pass_tds": _parse_float(row.get("passing_tds"), field="passing_tds"),
            "fantasy_points": _parse_float(
                row.get("fantasy_points_ppr"), field="fantasy_points_ppr"
            ),
        }
        off_bucket = off_sums[(group, team, week)]
        def_bucket = def_sums[(group, opponent, week)]
        for field_name, value in bag.items():
            off_bucket[field_name] += value
            def_bucket[field_name] += value

    return _bucket_by_group(off_sums), _bucket_by_group(def_sums), player_position


def _bucket_by_group(
    sums: dict[tuple[str, str, int], dict[str, float]],
) -> dict[str, dict[tuple[str, int], PositionalWeekRate]]:
    out: dict[str, dict[tuple[str, int], PositionalWeekRate]] = defaultdict(dict)
    for (group, team, week), bag in sums.items():
        out[group][(team, week)] = PositionalWeekRate(**bag)
    return dict(out)


def parse_alignment_csv(text: str) -> dict[tuple[str, int], str]:
    """Map (game_id, play_id) -> raw alignment string.

    Joins on `nflverse_game_id` / `nflverse_play_id` (FTN charting's own
    cross-reference to nflverse PBP IDs, per the nflreadr data dictionary).
    Returns an empty mapping when `ALIGNMENT_COLUMN` is absent — see the
    module-level "Alignment data" note for why that is the expected case
    against the current public release.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or ALIGNMENT_COLUMN not in reader.fieldnames:
        return {}

    out: dict[tuple[str, int], str] = {}
    for row in reader:
        game_id = row.get("nflverse_game_id") or row.get("game_id") or ""
        play_id = _parse_int(row.get("nflverse_play_id") or row.get("play_id"))
        alignment = row.get(ALIGNMENT_COLUMN)
        if not game_id or play_id is None or not alignment:
            continue
        out[(game_id, play_id)] = alignment
    return out


class _RateAccumulator:
    """Mutable per team-week OFF or DEF play-level rate accumulator."""

    __slots__ = (
        "pass_plays",
        "epa_pass_sum",
        "epa_pass_n",
        "xplsv_pass_n",
        "run_plays",
        "epa_run_sum",
        "epa_run_n",
        "xplsv_run_n",
        "proe_sum",
        "proe_n",
    )

    def __init__(self) -> None:
        self.pass_plays = 0
        self.epa_pass_sum = 0.0
        self.epa_pass_n = 0
        self.xplsv_pass_n = 0
        self.run_plays = 0
        self.epa_run_sum = 0.0
        self.epa_run_n = 0
        self.xplsv_run_n = 0
        self.proe_sum = 0.0
        self.proe_n = 0

    def to_slice(self, *, team: str, week: int, side: Literal["off", "def"]) -> TeamRateSlice:
        return TeamRateSlice(
            team=team,
            week=week,
            side=side,
            proe=(self.proe_sum / self.proe_n * 100.0) if self.proe_n else None,
            pass_plays=float(self.pass_plays),
            epa_pass=(self.epa_pass_sum / self.epa_pass_n) if self.epa_pass_n else None,
            xplsv_pass=(self.xplsv_pass_n / self.pass_plays) if self.pass_plays else None,
            run_plays=float(self.run_plays),
            epa_run=(self.epa_run_sum / self.epa_run_n) if self.epa_run_n else None,
            xplsv_run=(self.xplsv_run_n / self.run_plays) if self.run_plays else None,
        )


def _empty_out_slot_sums() -> dict[str, float]:
    return dict.fromkeys(_RATE_FIELDS, 0.0)


def parse_play_by_play(
    text: str,
    *,
    season: int,
    player_position: dict[str, str],
    alignment_by_key: dict[tuple[str, int], str],
) -> tuple[
    list[DriveOutcome],
    list[PassPlay],
    list[TeamRateSlice],
    list[TeamRateSlice],
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
    dict[str, dict[tuple[str, int], PositionalWeekRate]],
]:
    """Parse one season of nflverse PBP into drives, plays, and rate slices.

    Columns used (verified against a live `play_by_play_2025.csv.gz` header
    on 2026-11-08): `season`, `season_type`, `week`, `game_id`, `play_id`,
    `posteam`, `defteam`, `drive`, `qb_kneel`, `pass_attempt`, `rush_attempt`,
    `yards_gained`, `epa`, `xpass`, `series_success`, `touchdown`,
    `complete_pass`, `receiver_player_id`.

    Drive success = any non-kneel play in the drive has `series_success == 1`
    or `touchdown == 1` (first down or score); kneel-only drives are dropped
    entirely rather than counted as a failure, per the spec's "exclude QB
    kneels" rule.
    """
    reader = csv.DictReader(io.StringIO(text))
    _ensure_csv_headers(reader.fieldnames, _PBP_REQUIRED_HEADERS, source="play_by_play")

    # (team, week, drive_id) -> {"success": bool, "has_play": bool}
    drive_state: dict[tuple[str, int, str], dict[str, bool]] = {}
    pass_plays: list[PassPlay] = []
    off_rates: dict[tuple[str, int], _RateAccumulator] = defaultdict(_RateAccumulator)
    def_rates: dict[tuple[str, int], _RateAccumulator] = defaultdict(_RateAccumulator)
    out_wr_off: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_out_slot_sums)
    out_wr_def: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_out_slot_sums)
    slot_wr_off: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_out_slot_sums)
    slot_wr_def: dict[tuple[str, int], dict[str, float]] = defaultdict(_empty_out_slot_sums)

    for row in reader:
        row_season = _parse_int(row.get("season"))
        if row_season is not None and row_season != season:
            continue
        if (row.get("season_type") or "").upper() not in ("REG", "REGULAR"):
            continue
        week = _parse_int(row.get("week"))
        if week is None or week < 1 or week > 18:
            continue
        posteam = normalize_team(row.get("posteam") or "")
        defteam = normalize_team(row.get("defteam") or "")
        if not posteam or not defteam:
            continue  # e.g. kickoffs/timeouts with no recorded possession team

        is_kneel = _parse_bool(row.get("qb_kneel"))
        drive_id = row.get("drive") or ""
        if drive_id:
            key = (posteam, week, drive_id)
            state = drive_state.setdefault(key, {"success": False, "has_play": False})
            if not is_kneel:
                state["has_play"] = True
                if _parse_bool(row.get("series_success")) or _parse_bool(row.get("touchdown")):
                    state["success"] = True

        is_pass = _parse_bool(row.get("pass_attempt"))
        is_rush = _parse_bool(row.get("rush_attempt"))
        if (is_pass or is_rush) and not is_kneel:
            xpass = _parse_optional_float(row.get("xpass"), field="xpass")
            pass_plays.append(PassPlay(team=posteam, week=week, is_pass=is_pass, xpass=xpass))

            epa = _parse_optional_float(row.get("epa"), field="epa")
            yards = _parse_float(row.get("yards_gained"), field="yards_gained")
            off_acc = off_rates[(posteam, week)]
            def_acc = def_rates[(defteam, week)]

            if xpass is not None:
                delta = (1.0 if is_pass else 0.0) - xpass
                off_acc.proe_sum += delta
                off_acc.proe_n += 1
                def_acc.proe_sum += delta
                def_acc.proe_n += 1

            if is_pass:
                off_acc.pass_plays += 1
                def_acc.pass_plays += 1
                if epa is not None:
                    off_acc.epa_pass_sum += epa
                    off_acc.epa_pass_n += 1
                    def_acc.epa_pass_sum += epa
                    def_acc.epa_pass_n += 1
                if yards > 15:
                    off_acc.xplsv_pass_n += 1
                    def_acc.xplsv_pass_n += 1
            else:
                off_acc.run_plays += 1
                def_acc.run_plays += 1
                if epa is not None:
                    off_acc.epa_run_sum += epa
                    off_acc.epa_run_n += 1
                    def_acc.epa_run_sum += epa
                    def_acc.epa_run_n += 1
                if yards > 10:
                    off_acc.xplsv_run_n += 1
                    def_acc.xplsv_run_n += 1

        # Out/Slot WR: only pass attempts with a known receiver are eligible.
        receiver_id = row.get("receiver_player_id") or ""
        if is_pass and receiver_id:
            receiver_position = player_position.get(receiver_id)
            game_id = row.get("game_id") or ""
            play_id = _parse_int(row.get("play_id"))
            alignment_raw = (
                alignment_by_key.get((game_id, play_id)) if play_id is not None else None
            )
            alignment = classify_wr_alignment(
                position=receiver_position or "", alignment_raw=alignment_raw
            )
            if alignment in ("outside", "slot"):
                is_complete = _parse_bool(row.get("complete_pass"))
                yards = (
                    _parse_float(row.get("yards_gained"), field="yards_gained")
                    if is_complete
                    else 0.0
                )
                is_td = is_complete and _parse_bool(row.get("touchdown"))
                bag = {
                    "targets": 1.0,
                    "receptions": 1.0 if is_complete else 0.0,
                    "rec_yards": yards,
                    "rec_tds": 1.0 if is_td else 0.0,
                    "rush_att": 0.0,
                    "rush_yards": 0.0,
                    "rush_tds": 0.0,
                    "pass_yards": 0.0,
                    "pass_tds": 0.0,
                    "fantasy_points": 0.0,
                }
                if alignment == "outside":
                    off_sums, def_sums = out_wr_off, out_wr_def
                else:
                    off_sums, def_sums = slot_wr_off, slot_wr_def
                off_bucket = off_sums[(posteam, week)]
                def_bucket = def_sums[(defteam, week)]
                for field_name, value in bag.items():
                    off_bucket[field_name] += value
                    def_bucket[field_name] += value

    drives = [
        DriveOutcome(team=team, week=week, success=state["success"])
        for (team, week, _drive_id), state in drive_state.items()
        if state["has_play"]
    ]
    team_env_off = [
        acc.to_slice(team=team, week=week, side="off") for (team, week), acc in off_rates.items()
    ]
    team_env_def = [
        acc.to_slice(team=team, week=week, side="def") for (team, week), acc in def_rates.items()
    ]

    positional_off = {
        "out_wr": _finalize_out_slot(out_wr_off),
        "slot_wr": _finalize_out_slot(slot_wr_off),
    }
    positional_def = {
        "out_wr": _finalize_out_slot(out_wr_def),
        "slot_wr": _finalize_out_slot(slot_wr_def),
    }
    return drives, pass_plays, team_env_off, team_env_def, positional_off, positional_def


def _finalize_out_slot(
    sums: dict[tuple[str, int], dict[str, float]],
) -> dict[tuple[str, int], PositionalWeekRate]:
    out: dict[tuple[str, int], PositionalWeekRate] = {}
    for (team, week), bag in sums.items():
        fantasy_points = receiving_points(
            receptions=bag["receptions"], yards=bag["rec_yards"], tds=bag["rec_tds"], scoring="ppr"
        )
        out[(team, week)] = PositionalWeekRate(
            targets=bag["targets"],
            receptions=bag["receptions"],
            rec_yards=bag["rec_yards"],
            rec_tds=bag["rec_tds"],
            rush_att=0.0,
            rush_yards=0.0,
            rush_tds=0.0,
            pass_yards=0.0,
            pass_tds=0.0,
            fantasy_points=fantasy_points,
        )
    return out


def _validate_schedule_headers(text: str) -> None:
    reader = csv.DictReader(io.StringIO(text))
    _ensure_csv_headers(reader.fieldnames, _SCHEDULE_REQUIRED_HEADERS, source="schedules")


def _invert_schedule(
    team_week: dict[str, dict[int, str | None]],
) -> dict[int, dict[str, str | None]]:
    """Transpose SoS's team→week→opponent schedule into week→team→opponent."""
    by_week: dict[int, dict[str, str | None]] = {week: {} for week in WEEKS}
    for team, week_map in team_week.items():
        for week, opponent in week_map.items():
            by_week.setdefault(week, {})[team] = opponent
    return by_week


def load_workbook_dataset(
    season: int,
    *,
    http_get: HttpGetter | None = None,
    now: datetime | None = None,
) -> WorkbookDataset:
    """Download nflverse PBP + weekly stats + schedule and normalize them."""
    getter = http_get or default_http_get
    moment = now or datetime.now(UTC)

    try:
        pbp_bytes = getter(PBP_URL.format(season=season))
        stats_bytes = getter(STATS_URL.format(season=season))
        schedule_bytes = getter(SCHEDULES_URL)
        alignment_bytes = getter(FTN_CHARTING_URL.format(season=season))
    except WorkbookNflverseError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface as WorkbookNflverseError
        raise WorkbookNflverseError(f"nflverse download failed: {exc}") from exc

    try:
        pbp_text = _decode_csv_bytes(pbp_bytes)
        stats_text = _decode_csv_bytes(stats_bytes)
        schedule_text = schedule_bytes.decode("utf-8")
        alignment_text = _decode_csv_bytes(alignment_bytes)

        positional_off, positional_def, player_position = parse_positional_stats(
            stats_text, season=season
        )
        alignment_by_key = parse_alignment_csv(alignment_text)
        (
            drives,
            pass_plays,
            team_env_off,
            team_env_def,
            out_slot_off,
            out_slot_def,
        ) = parse_play_by_play(
            pbp_text,
            season=season,
            player_position=player_position,
            alignment_by_key=alignment_by_key,
        )
        positional_off = {**positional_off, **out_slot_off}
        positional_def = {**positional_def, **out_slot_def}

        _validate_schedule_headers(schedule_text)
        team_week_schedule = parse_schedule_csv(schedule_text, season=season)
        schedule = _invert_schedule(team_week_schedule)
        teams = sorted(team_week_schedule.keys()) or list(NFL_TEAMS)
    except WorkbookNflverseError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface parse failures uniformly
        raise WorkbookNflverseError(f"nflverse parse failed: {exc}") from exc

    return WorkbookDataset(
        season=season,
        fetched_at=moment.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        teams=teams,
        schedule=schedule,
        drives=drives,
        pass_plays=pass_plays,
        team_env_off=team_env_off,
        team_env_def=team_env_def,
        positional_off=positional_off,
        positional_def=positional_def,
    )
