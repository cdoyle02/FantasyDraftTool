"""Position usage shares from nflverse stats_player_week rows."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass

from draft_api.sos.calculate import Position, SKILL_POSITIONS
from draft_api.sos.nflverse import normalize_team
from draft_api.sos.tier2_snap import SnapPctIndex

# Columns required by build_usage_index (trimmed on snapshot refresh).
USAGE_STATS_FIELDS: tuple[str, ...] = (
    "season",
    "week",
    "season_type",
    "position",
    "team",
    "player_id",
    "gsis_id",
    "player_display_name",
    "player_name",
    "carries",
    "rush_attempts",
    "targets",
    "passing_yards",
)


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _row_eligible_for_usage(row: dict[str, str | None], *, season: int) -> bool:
    if (row.get("season_type") or "").upper() not in ("REG", "REGULAR"):
        return False
    row_season = _parse_int(row.get("season"))
    if row_season is not None and row_season != season:
        return False
    week = _parse_int(row.get("week"))
    if week is None or week < 1 or week > 18:
        return False
    row_pos = (row.get("position") or "").upper()
    if row_pos not in SKILL_POSITIONS:
        return False
    if not normalize_team(row.get("team") or ""):
        return False
    return True


def trim_usage_stats_row(row: dict[str, str | None]) -> dict[str, str | None]:
    """Keep only usage-index columns with non-empty values."""
    trimmed: dict[str, str | None] = {}
    for key in USAGE_STATS_FIELDS:
        value = row.get(key)
        if value is None or value == "":
            continue
        trimmed[key] = value
    return trimmed


def parse_usage_stats_csv(text: str, *, season: int) -> list[dict[str, str | None]]:
    """Parse nflverse stats_player_week CSV into trimmed usage-ready rows."""
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict[str, str | None]] = []
    for raw in reader:
        row = {key: (None if value == "" else value) for key, value in dict(raw).items()}
        if not _row_eligible_for_usage(row, season=season):
            continue
        trimmed = trim_usage_stats_row(row)
        if trimmed:
            out.append(trimmed)
    return out


@dataclass(frozen=True, slots=True)
class PlayerUsage:
    gsis_id: str | None
    player_name: str
    team: str
    position: Position
    usage_share: float | None


def _parse_float(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _row_in_scope(
    row: dict[str, str | None],
    *,
    position: Position,
    weeks: set[int],
    season: int | None = None,
) -> bool:
    if (row.get("season_type") or "").upper() not in ("REG", "REGULAR"):
        return False
    row_season = _parse_int(row.get("season"))
    if season is not None and row_season is not None and row_season != season:
        return False
    week = _parse_int(row.get("week"))
    if week is None or week not in weeks:
        return False
    row_pos = (row.get("position") or "").upper()
    if row_pos != position:
        return False
    team = normalize_team(row.get("team") or "")
    if not team:
        return False
    return True


def _player_key(row: dict[str, str | None]) -> tuple[str, str, str]:
    player_id = (row.get("player_id") or row.get("gsis_id") or "").strip()
    name = (row.get("player_display_name") or row.get("player_name") or player_id).strip()
    team = normalize_team(row.get("team") or "")
    return (player_id or name, name, team)


def build_usage_index(
    stats_rows: list[dict[str, str | None]],
    *,
    position: Position,
    weeks: set[int],
    season: int | None = None,
) -> list[PlayerUsage]:
    """Mean weekly usage share for each player over `weeks` (bye weeks excluded)."""
    if position not in SKILL_POSITIONS:
        raise ValueError(f"usage shares unsupported for position {position!r}")

    scoped = [
        row for row in stats_rows if _row_in_scope(row, position=position, weeks=weeks, season=season)
    ]
    if not scoped:
        return []

    if position == "QB":
        return _qb_usage_index(scoped)

    weekly_shares: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    team_week_totals: dict[tuple[str, int], float] = defaultdict(float)
    player_meta: dict[tuple[str, str, str], tuple[str | None, str]] = {}

    for row in scoped:
        week = _parse_int(row.get("week"))
        if week is None:
            continue
        team = normalize_team(row.get("team") or "")
        key = _player_key(row)
        player_meta[key] = (
            (row.get("player_id") or row.get("gsis_id") or None),
            team,
        )
        if position == "RB":
            volume = _parse_float(row.get("carries") or row.get("rush_attempts"))
        else:
            volume = _parse_float(row.get("targets"))
        team_week_totals[(team, week)] += volume

    for row in scoped:
        week = _parse_int(row.get("week"))
        if week is None:
            continue
        team = normalize_team(row.get("team") or "")
        total = team_week_totals.get((team, week), 0.0)
        if total <= 0.0:
            continue
        if position == "RB":
            volume = _parse_float(row.get("carries") or row.get("rush_attempts"))
        else:
            volume = _parse_float(row.get("targets"))
        if volume <= 0.0:
            continue
        key = _player_key(row)
        weekly_shares[key].append(volume / total)

    out: list[PlayerUsage] = []
    for key, shares in weekly_shares.items():
        _pid, name, team = key
        gsis_id, meta_team = player_meta.get(key, (None, team))
        if not shares:
            continue
        out.append(
            PlayerUsage(
                gsis_id=gsis_id,
                player_name=name,
                team=meta_team,
                position=position,
                usage_share=sum(shares) / len(shares),
            )
        )
    out.sort(key=lambda row: (-(row.usage_share or 0.0), row.player_name))
    return out


def _qb_usage_index(rows: list[dict[str, str | None]]) -> list[PlayerUsage]:
    """Starter = most passing yards in window; starter share 1.0, others null."""
    yards_by_player: dict[tuple[str, str, str], float] = defaultdict(float)
    meta: dict[tuple[str, str, str], tuple[str | None, str]] = {}
    for row in rows:
        key = _player_key(row)
        yards_by_player[key] += _parse_float(row.get("passing_yards"))
        meta[key] = (
            (row.get("player_id") or row.get("gsis_id") or None),
            normalize_team(row.get("team") or ""),
        )

    by_team: dict[str, list[tuple[tuple[str, str, str], float]]] = defaultdict(list)
    for key, yards in yards_by_player.items():
        _pid, _name, team = key
        by_team[team].append((key, yards))

    out: list[PlayerUsage] = []
    for team, players in sorted(by_team.items()):
        players.sort(key=lambda item: (-item[1], item[0][1]))
        starter_key, starter_yards = players[0]
        for key, yards in players:
            _pid, name, _team = key
            gsis_id, meta_team = meta[key]
            if yards <= 0.0 and key != starter_key:
                share = None
            elif key == starter_key and starter_yards > 0.0:
                share = 1.0
            elif key == starter_key:
                share = None
            else:
                share = None
            out.append(
                PlayerUsage(
                    gsis_id=gsis_id,
                    player_name=name,
                    team=meta_team,
                    position="QB",
                    usage_share=share,
                )
            )
    return out
