"""Download and normalize nflverse weekly player stats + schedules."""

from __future__ import annotations

import csv
import gzip
import io
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from draft_api.sos.calculate import (
    POSITIONS,
    SKILL_POSITIONS,
    WEEKS,
    CompletedGame,
    Position,
)
from draft_api.sos.dst_scoring import dst_fantasy_points

HttpGetter = Callable[[str], bytes]

STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{season}.csv.gz"
)
TEAM_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_team/stats_team_week_{season}.csv.gz"
)
SCHEDULES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; FantasyDraftTool/1.0; "
    "+https://github.com/nflverse/nflverse-data)"
)

# nflverse / ESPN abbreviations → app abbreviations.
TEAM_ALIASES: dict[str, str] = {
    "LA": "LAR",
    "WSH": "WAS",
}

NFL_TEAMS: tuple[str, ...] = (
    "ARI",
    "ATL",
    "BAL",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HOU",
    "IND",
    "JAX",
    "KC",
    "LV",
    "LAC",
    "LAR",
    "MIA",
    "MIN",
    "NE",
    "NO",
    "NYG",
    "NYJ",
    "PHI",
    "PIT",
    "SF",
    "SEA",
    "TB",
    "TEN",
    "WAS",
)


class NflverseError(RuntimeError):
    """Raised when nflverse downloads or parsing fail."""


@dataclass(frozen=True, slots=True)
class SosDataset:
    """Normalized season data ready for the SoS calculator."""

    season: int
    fetched_at: str
    games: list[CompletedGame]
    schedule: dict[str, dict[int, str | None]]
    teams: list[str]
    usage_stats: tuple[dict[str, str | None], ...] = field(default_factory=tuple)

    @property
    def rated_through_week(self) -> int:
        if not self.games:
            return 0
        return max(game.week for game in self.games)


def normalize_team(abbrev: str) -> str:
    raw = abbrev.strip().upper()
    return TEAM_ALIASES.get(raw, raw)


def default_http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise NflverseError(f"nflverse HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise NflverseError(f"nflverse network error for {url}: {exc.reason}") from exc


def _parse_float(value: str) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_int(value: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _empty_points() -> dict[Position, float]:
    return {pos: 0.0 for pos in POSITIONS}


def parse_stats_csv(text: str, *, season: int) -> dict[tuple[int, str, str], dict[Position, float]]:
    """Aggregate player PPR points into offense→defense game totals by skill position."""
    reader = csv.DictReader(io.StringIO(text))
    buckets: dict[tuple[int, str, str], dict[Position, float]] = defaultdict(_empty_points)

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
        if position not in SKILL_POSITIONS:
            continue
        offense = normalize_team(row.get("team") or "")
        defense = normalize_team(row.get("opponent_team") or "")
        if not offense or not defense:
            continue
        points = _parse_float(row.get("fantasy_points_ppr") or "")
        buckets[(week, offense, defense)][position] += points  # type: ignore[index]

    return buckets


def schedule_points_allowed(text: str, *, season: int) -> dict[tuple[int, str], float]:
    """Map (week, team) → points scored against that team (opponent's score)."""
    reader = csv.DictReader(io.StringIO(text))
    allowed: dict[tuple[int, str], float] = {}
    for row in reader:
        row_season = _parse_int(row.get("season", ""))
        if row_season != season:
            continue
        game_type = (row.get("game_type") or "").upper()
        if game_type not in ("REG", "REGULAR"):
            continue
        week = _parse_int(row.get("week", ""))
        if week is None:
            continue
        away_score_raw = row.get("away_score")
        home_score_raw = row.get("home_score")
        if away_score_raw in (None, "") or home_score_raw in (None, ""):
            continue
        away = normalize_team(row.get("away_team") or "")
        home = normalize_team(row.get("home_team") or "")
        if not away or not home:
            continue
        away_score = _parse_float(away_score_raw)
        home_score = _parse_float(home_score_raw)
        # Points allowed by away D/ST = home score, and vice versa.
        allowed[(week, away)] = home_score
        allowed[(week, home)] = away_score
    return allowed


def parse_team_dst_csv(
    text: str,
    *,
    season: int,
    points_allowed_by_team: dict[tuple[int, str], float],
) -> dict[tuple[int, str, str], float]:
    """Return (week, dst_team, offense_faced) → ESPN-style DST fantasy points.

    Stored so FPA aggregates by offense_faced (= how many DST points that offense
    allows), matching skill-position SoS polarity.
    """
    reader = csv.DictReader(io.StringIO(text))
    out: dict[tuple[int, str, str], float] = {}
    for row in reader:
        row_season = _parse_int(row.get("season", ""))
        if row_season is not None and row_season != season:
            continue
        if (row.get("season_type") or "").upper() not in ("REG", "REGULAR"):
            continue
        week = _parse_int(row.get("week", ""))
        if week is None or week < 1 or week > 18:
            continue
        dst_team = normalize_team(row.get("team") or "")
        offense_faced = normalize_team(row.get("opponent_team") or "")
        if not dst_team or not offense_faced:
            continue
        blocked = (
            _parse_float(row.get("def_punt_blocks") or "")
            + _parse_float(row.get("def_fg_blocks") or "")
            + _parse_float(row.get("def_pat_blocks") or "")
        )
        special_tds = _parse_float(row.get("special_teams_tds") or "") + _parse_float(
            row.get("pt_return_tds") or ""
        )
        fantasy = dst_fantasy_points(
            sacks=_parse_float(row.get("def_sacks") or ""),
            interceptions=_parse_float(row.get("def_interceptions") or ""),
            fumble_recoveries=_parse_float(row.get("fumble_recovery_opp") or ""),
            defensive_tds=_parse_float(row.get("def_tds") or ""),
            special_teams_tds=special_tds,
            safeties=_parse_float(row.get("def_safeties") or ""),
            blocked_kicks=blocked,
            points_allowed=points_allowed_by_team.get((week, dst_team), 0.0),
        )
        # offense = DST scoring team, defense = offense that allowed those DST points
        out[(week, dst_team, offense_faced)] = fantasy
    return out


def merge_skill_and_dst(
    skill: dict[tuple[int, str, str], dict[Position, float]],
    dst: dict[tuple[int, str, str], float],
) -> list[CompletedGame]:
    """Combine skill and DST buckets into CompletedGame rows."""
    keys = set(skill) | set(dst)
    games: list[CompletedGame] = []
    for week, offense, defense in sorted(keys):
        points = dict(skill.get((week, offense, defense), _empty_points()))
        if (week, offense, defense) in dst:
            points["DST"] = dst[(week, offense, defense)]
        games.append(
            CompletedGame(week=week, offense=offense, defense=defense, points=points)
        )
    return games


def parse_schedule_csv(text: str, *, season: int) -> dict[str, dict[int, str | None]]:
    """Build team → week → opponent (None = bye) for regular-season games."""
    reader = csv.DictReader(io.StringIO(text))
    opponents: dict[str, dict[int, str]] = defaultdict(dict)
    teams_seen: set[str] = set()

    for row in reader:
        row_season = _parse_int(row.get("season", ""))
        if row_season != season:
            continue
        game_type = (row.get("game_type") or "").upper()
        if game_type not in ("REG", "REGULAR"):
            continue
        week = _parse_int(row.get("week", ""))
        if week is None or week < 1 or week > 18:
            continue
        away = normalize_team(row.get("away_team") or "")
        home = normalize_team(row.get("home_team") or "")
        if not away or not home:
            continue
        opponents[away][week] = home
        opponents[home][week] = away
        teams_seen.add(away)
        teams_seen.add(home)

    team_list = sorted(teams_seen) if teams_seen else list(NFL_TEAMS)
    return {
        team: {week: opponents.get(team, {}).get(week) for week in WEEKS}
        for team in team_list
    }


def completed_game_keys_from_schedule(text: str, *, season: int) -> set[tuple[int, str, str]]:
    """Return (week, offense, defense) pairs for games with both scores present."""
    reader = csv.DictReader(io.StringIO(text))
    keys: set[tuple[int, str, str]] = set()
    for row in reader:
        row_season = _parse_int(row.get("season", ""))
        if row_season != season:
            continue
        game_type = (row.get("game_type") or "").upper()
        if game_type not in ("REG", "REGULAR"):
            continue
        week = _parse_int(row.get("week", ""))
        if week is None:
            continue
        away_score = row.get("away_score")
        home_score = row.get("home_score")
        if away_score in (None, "") or home_score in (None, ""):
            continue
        away = normalize_team(row.get("away_team") or "")
        home = normalize_team(row.get("home_team") or "")
        if not away or not home:
            continue
        keys.add((week, away, home))
        keys.add((week, home, away))
    return keys


def _decode_csv_bytes(raw: bytes) -> str:
    try:
        return gzip.decompress(raw).decode("utf-8")
    except OSError:
        return raw.decode("utf-8")


def decode_nflverse_csv_bytes(raw: bytes) -> str:
    """Decode gzipped or plain nflverse CSV bytes."""
    return _decode_csv_bytes(raw)


def load_usage_stats(
    season: int,
    *,
    http_get: HttpGetter | None = None,
) -> tuple[dict[str, str | None], ...]:
    """Download and trim stats_player_week rows for opportunity / snapshot refresh."""
    from draft_api.sos.usage import parse_usage_stats_csv

    getter = http_get or default_http_get
    try:
        raw = getter(STATS_URL.format(season=season))
    except Exception as exc:  # noqa: BLE001 - surfaced to callers as NflverseError
        raise NflverseError(f"nflverse stats_player_week download failed: {exc}") from exc
    text = _decode_csv_bytes(raw)
    try:
        rows = parse_usage_stats_csv(text, season=season)
    except UnicodeDecodeError as exc:
        raise NflverseError(f"nflverse stats_player_week parse failed: {exc}") from exc
    return tuple(rows)


def load_sos_dataset(
    season: int,
    *,
    http_get: HttpGetter | None = None,
    now: datetime | None = None,
) -> SosDataset:
    """Download nflverse stats + schedule and normalize into an SoS dataset."""
    getter = http_get or default_http_get
    moment = now or datetime.now(timezone.utc)

    try:
        stats_bytes = getter(STATS_URL.format(season=season))
        team_bytes = getter(TEAM_STATS_URL.format(season=season))
        schedule_bytes = getter(SCHEDULES_URL)
    except NflverseError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface as NflverseError for API fallback
        raise NflverseError(f"nflverse download failed: {exc}") from exc

    stats_text = _decode_csv_bytes(stats_bytes)
    team_text = _decode_csv_bytes(team_bytes)
    schedule_text = schedule_bytes.decode("utf-8")

    schedule = parse_schedule_csv(schedule_text, season=season)
    completed_keys = completed_game_keys_from_schedule(schedule_text, season=season)
    points_allowed = schedule_points_allowed(schedule_text, season=season)
    skill = parse_stats_csv(stats_text, season=season)
    dst = parse_team_dst_csv(team_text, season=season, points_allowed_by_team=points_allowed)
    all_games = merge_skill_and_dst(skill, dst)

    # Prefer games with official scores. If the schedule has no scores yet
    # (early preseason), keep every parsed stats row.
    if completed_keys:
        games = [
            game
            for game in all_games
            if (game.week, game.offense, game.defense) in completed_keys
        ]
    else:
        games = all_games

    teams = sorted(schedule.keys()) or list(NFL_TEAMS)
    return SosDataset(
        season=season,
        fetched_at=moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        games=games,
        schedule=schedule,
        teams=teams,
    )
