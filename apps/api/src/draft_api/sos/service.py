"""Assemble strength-of-schedule API payloads from live nflverse or snapshot."""

from __future__ import annotations

import csv
import gzip
import io
import logging
from datetime import datetime, timezone
from typing import Any

from draft_api.nfl_week import fantasy_week_number, season_week1_tuesday_from_env
from draft_api.odds.cache import TtlCache
from draft_api.sos.calculate import SHRINK_K, Metric, Position, SosWindow, build_sos_payload, sos_payload_to_dict
from draft_api.sos.tier1 import (
    build_defense_softness_index,
    build_player_opportunity,
    build_tier1_grid,
    tier1_payload_to_dict,
)
from draft_api.sos.usage import build_usage_index
from draft_api.sos.nflverse import STATS_URL, HttpGetter, NflverseError, SosDataset, default_http_get, load_sos_dataset
from draft_api.sos.snapshot import SnapshotError, read_packaged_snapshot

logger = logging.getLogger("fantasy_draft_api.sos")

DEFAULT_SEASON = 2026
_dataset_cache: TtlCache[SosDataset] = TtlCache(ttl_seconds=6 * 3600)
_http_get_override: HttpGetter | None = None
_dataset_override: SosDataset | None = None
_stats_rows_override: list[dict[str, str | None]] | None = None


def set_sos_http_get(http_get: HttpGetter | None) -> None:
    """Test hook: override nflverse downloader (None restores default)."""
    global _http_get_override
    _http_get_override = http_get
    _dataset_cache.clear()


def set_sos_dataset_override(dataset: SosDataset | None) -> None:
    """Test hook: inject a fully built dataset (skips download + snapshot)."""
    global _dataset_override
    _dataset_override = dataset
    _dataset_cache.clear()


def set_sos_stats_rows_override(rows: list[dict[str, str | None]] | None) -> None:
    """Test hook: inject nflverse stats_player_week rows for opportunity."""
    global _stats_rows_override
    _stats_rows_override = rows


def set_sos_cache_ttl(seconds: float) -> None:
    """Test hook: rebuild cache with a custom TTL."""
    global _dataset_cache
    _dataset_cache = TtlCache(ttl_seconds=seconds)


def clear_sos_cache() -> None:
    _dataset_cache.clear()


def _decode_stats_csv(raw: bytes) -> str:
    try:
        return gzip.decompress(raw).decode("utf-8")
    except OSError:
        return raw.decode("utf-8")


def _resolve_stats_rows(season: int) -> list[dict[str, str | None]]:
    if _stats_rows_override is not None:
        return _stats_rows_override
    getter = _http_get_override or default_http_get
    raw = getter(STATS_URL.format(season=season))
    text = _decode_stats_csv(raw)
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _default_window(now: datetime) -> tuple[int, int]:
    week = fantasy_week_number(now, season_week1_tuesday=season_week1_tuesday_from_env())
    start = max(1, min(18, week))
    end = 17
    if start > end:
        # Late season / week 18: still return a valid single-week window.
        end = start
    return start, end


def resolve_dataset(season: int, *, now: datetime | None = None) -> tuple[SosDataset, str, bool]:
    """Return (dataset, source, stale). Prefer live nflverse; fall back to snapshot."""
    if _dataset_override is not None:
        return _dataset_override, "fixture", False

    cached = _dataset_cache.get()
    if cached is not None and cached.season == season:
        return cached, "nflverse", False

    try:
        dataset = load_sos_dataset(season, http_get=_http_get_override, now=now)
        _dataset_cache.set(dataset)
        return dataset, "nflverse", False
    except NflverseError as exc:
        logger.warning("nflverse SoS fetch failed; using snapshot: %s", exc)
        try:
            snapshot = read_packaged_snapshot(season)
            return snapshot, "snapshot", True
        except SnapshotError as snap_exc:
            raise NflverseError(
                f"nflverse unavailable ({exc}) and snapshot missing ({snap_exc})"
            ) from snap_exc


def build_strength_of_schedule_response(
    *,
    position: Position,
    metric: Metric,
    start_week: int | None = None,
    end_week: int | None = None,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    default_start, default_end = _default_window(moment)
    window_start = default_start if start_week is None else start_week
    window_end = default_end if end_week is None else end_week

    dataset, source, stale = resolve_dataset(season, now=moment)
    payload = build_sos_payload(
        season=dataset.season,
        position=position,
        metric=metric,
        start_week=window_start,
        end_week=window_end,
        games=dataset.games,
        season_schedule=dataset.schedule,
        teams=dataset.teams,
    )
    fetched_at = dataset.fetched_at or moment.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return sos_payload_to_dict(payload, fetched_at=fetched_at, source=source, stale=stale)


def build_tier1_strength_of_schedule_response(
    *,
    position: Position,
    window: SosWindow = "l8",
    start_week: int | None = None,
    end_week: int | None = None,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    default_start, default_end = _default_window(moment)
    window_start = default_start if start_week is None else start_week
    window_end = default_end if end_week is None else end_week

    dataset, source, stale = resolve_dataset(season, now=moment)
    payload = build_tier1_grid(
        season=dataset.season,
        position=position,
        window=window,
        start_week=window_start,
        end_week=window_end,
        games=dataset.games,
        season_schedule=dataset.schedule,
        teams=dataset.teams,
    )
    fetched_at = dataset.fetched_at or moment.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return tier1_payload_to_dict(payload, fetched_at=fetched_at, source=source, stale=stale)


class LeagueJoinUnavailableError(LookupError):
    """Raised when opportunity is requested with leagueId before roster join ships."""


def build_tier1_opportunity_response(
    *,
    position: Position,
    window: SosWindow = "l8",
    week: int | None = None,
    season: int = DEFAULT_SEASON,
    league_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Nflverse player opportunity rows (softness × usage); ESPN join is wave 3."""
    if position == "DST":
        raise ValueError("DST is excluded from Tier 1 opportunity")
    if league_id:
        raise LeagueJoinUnavailableError(f"league roster join not configured for {league_id!r}")

    moment = now or datetime.now(timezone.utc)
    dataset, source, stale = resolve_dataset(season, now=moment)
    target_week = week
    if target_week is None:
        target_week = fantasy_week_number(
            moment, season_week1_tuesday=season_week1_tuesday_from_env()
        )
    if target_week < 1 or target_week > 18:
        raise ValueError(f"invalid week {target_week}")

    try:
        stats_rows = _resolve_stats_rows(season)
    except NflverseError as exc:
        logger.warning("stats_player_week unavailable for opportunity: %s", exc)
        stats_rows = []

    rated_through, rating_weeks, softness = build_defense_softness_index(
        position=position,
        window=window,
        games=dataset.games,
        teams=dataset.teams,
    )
    usage = build_usage_index(
        stats_rows,
        position=position,
        weeks=set(rating_weeks),
        season=season,
    )
    players = build_player_opportunity(
        usage_index=usage,
        defense_softness=softness,
        schedule=dataset.schedule,
        week=target_week,
    )
    fetched_at = dataset.fetched_at or moment.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return {
        "season": season,
        "position": position,
        "window": window,
        "week": target_week,
        "ratedThroughWeek": rated_through,
        "ratingWeeks": list(rating_weeks),
        "shrinkK": SHRINK_K,
        "fetchedAt": fetched_at,
        "source": source,
        "stale": stale,
        "players": players,
    }
