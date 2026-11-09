"""Assemble strength-of-schedule API payloads from live nflverse or snapshot."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from draft_api.nfl_week import fantasy_week_number, season_week1_tuesday_from_env
from draft_api.odds.cache import TtlCache
from draft_api.sos.calculate import SHRINK_K, Metric, Position, SosWindow, build_sos_payload, sos_payload_to_dict
from draft_api.implied_totals import GameLine
from draft_api.sos.tier1 import (
    build_defense_softness_index,
    build_player_opportunity,
    build_tier1_grid,
    tier1_payload_to_dict,
)
from draft_api.sos.tier2 import (
    build_tier2_grid,
    build_tier2_player_opportunity,
    tier2_payload_to_dict,
)
from draft_api.sos.tier2_epa import Tier2EpaPosition, build_defense_epa_softness_index
from draft_api.sos.tier2_snap import (
    DEFAULT_MIN_OFFENSE_SNAP_PCT,
    SNAP_COUNTS_URL,
    build_snap_pct_index,
    decode_snap_csv,
    parse_snap_counts_csv,
)
from draft_api.espn_leagues import get_league
from draft_api.espn_roster import EspnRosterError, fetch_league_roster
from draft_api.espn_available_dst import espn_credentials_from_env
from draft_api.sos.roster_join import join_roster_opportunity
from draft_api.sos.usage import build_usage_index
from draft_api.sos.nflverse import (
    HttpGetter,
    NflverseError,
    SosDataset,
    default_http_get,
    load_sos_dataset,
    load_usage_stats,
)
from draft_api.sos.snapshot import SnapshotError, read_packaged_snapshot

logger = logging.getLogger("fantasy_draft_api.sos")

DEFAULT_SEASON = 2026
_dataset_cache: TtlCache[SosDataset] = TtlCache(ttl_seconds=6 * 3600)
_http_get_override: HttpGetter | None = None
_dataset_override: SosDataset | None = None
_stats_rows_override: list[dict[str, str | None]] | None = None
_snap_rows_override: list[dict[str, str | None]] | None = None


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


def set_sos_snap_rows_override(rows: list[dict[str, str | None]] | None) -> None:
    """Test hook: inject nflverse snap_counts rows for Tier 2 usage."""
    global _snap_rows_override
    _snap_rows_override = rows


def set_sos_cache_ttl(seconds: float) -> None:
    """Test hook: rebuild cache with a custom TTL."""
    global _dataset_cache
    _dataset_cache = TtlCache(ttl_seconds=seconds)


def clear_sos_cache() -> None:
    _dataset_cache.clear()


def _resolve_stats_rows(
    season: int,
    dataset: SosDataset,
) -> tuple[list[dict[str, str | None]], bool]:
    """Return (rows, used_packaged_usage)."""
    if _stats_rows_override is not None:
        return _stats_rows_override, False
    try:
        return list(load_usage_stats(season, http_get=_http_get_override)), False
    except NflverseError as exc:
        logger.warning("stats_player_week live fetch failed for opportunity: %s", exc)
    if dataset.usage_stats:
        return list(dataset.usage_stats), True
    try:
        snapshot = read_packaged_snapshot(season)
    except SnapshotError as exc:
        logger.warning("packaged usage stats unavailable: %s", exc)
        return [], False
    if snapshot.usage_stats:
        return list(snapshot.usage_stats), True
    return [], False


def _resolve_snap_rows(season: int) -> tuple[list[dict[str, str | None]], bool]:
    if _snap_rows_override is not None:
        return _snap_rows_override, False
    getter = _http_get_override or default_http_get
    try:
        raw = getter(SNAP_COUNTS_URL.format(season=season))
        text = decode_snap_csv(raw)
        return parse_snap_counts_csv(text, season=season), False
    except Exception as exc:  # noqa: BLE001 — snap_counts is optional enrichment
        logger.warning("snap_counts live fetch failed for Tier 2: %s", exc)
        return [], False


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


def build_tier1_opportunity_response(
    *,
    position: Position,
    window: SosWindow = "l8",
    week: int | None = None,
    season: int = DEFAULT_SEASON,
    league_id: str | None = None,
    now: datetime | None = None,
    espn_http_json: HttpGetter | None = None,
) -> dict[str, Any]:
    """Nflverse player opportunity rows (softness × usage); optional ESPN roster overlay."""
    if position == "DST":
        raise ValueError("DST is excluded from Tier 1 opportunity")
    league_meta: dict[str, Any] = {}
    if league_id:
        league = get_league(league_id)
        league_meta = {"leagueId": league["id"], "leagueName": league["name"]}

    moment = now or datetime.now(timezone.utc)
    dataset, source, stale = resolve_dataset(season, now=moment)
    target_week = week
    if target_week is None:
        target_week = fantasy_week_number(
            moment, season_week1_tuesday=season_week1_tuesday_from_env()
        )
    if target_week < 1 or target_week > 18:
        raise ValueError(f"invalid week {target_week}")

    stats_rows, _usage_from_snapshot = _resolve_stats_rows(season, dataset)
    usage_unavailable = len(stats_rows) == 0

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
    join_stats: dict[str, int] | None = None
    overlay_error: str | None = None
    if league_id:
        try:
            espn_s2, swid, cred_season = espn_credentials_from_env()
            roster_season = season or cred_season
            if espn_http_json is not None:
                espn_s2 = espn_s2 or "test-espn-s2"
                swid = swid or "{00000000-0000-0000-0000-000000000000}"
            roster = fetch_league_roster(
                league_id=league_id,
                season=roster_season,
                espn_s2=espn_s2,
                swid=swid,
                http_json=espn_http_json,
            )
            players, join_stats = join_roster_opportunity(
                roster, players, position=position
            )
        except EspnRosterError as exc:
            logger.warning("SoS Tier1 ESPN roster join unavailable: %s", exc)
            players = []
            join_stats = {"matched": 0, "unmatched": 0, "skippedPosition": 0}
            overlay_error = "espn_unavailable"
    fetched_at = dataset.fetched_at or moment.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    body: dict[str, Any] = {
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
    body.update(league_meta)
    if join_stats is not None:
        body["joinStats"] = join_stats
    if overlay_error:
        body["overlayError"] = overlay_error
    if usage_unavailable:
        body["usageUnavailable"] = True
    return body


def build_tier2_strength_of_schedule_response(
    *,
    position: Tier2EpaPosition,
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
    stats_rows, _ = _resolve_stats_rows(season, dataset)
    payload = build_tier2_grid(
        season=dataset.season,
        position=position,
        window=window,
        start_week=window_start,
        end_week=window_end,
        games=dataset.games,
        stats_rows=stats_rows,
        season_schedule=dataset.schedule,
        teams=dataset.teams,
    )
    fetched_at = dataset.fetched_at or moment.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    return tier2_payload_to_dict(payload, fetched_at=fetched_at, source=source, stale=stale)


def build_tier2_opportunity_response(
    *,
    position: Tier2EpaPosition,
    window: SosWindow = "l8",
    week: int | None = None,
    season: int = DEFAULT_SEASON,
    league_id: str | None = None,
    now: datetime | None = None,
    espn_http_json: HttpGetter | None = None,
    game_lines: list[GameLine] | None = None,
) -> dict[str, Any]:
    if position not in ("QB", "RB", "WR", "TE"):
        raise ValueError(
            f"Tier 2 opportunity supports QB, RB, WR, and TE only (got {position!r})"
        )

    league_meta: dict[str, Any] = {}
    if league_id:
        league = get_league(league_id)
        league_meta = {"leagueId": league["id"], "leagueName": league["name"]}

    moment = now or datetime.now(timezone.utc)
    dataset, source, stale = resolve_dataset(season, now=moment)
    target_week = week
    if target_week is None:
        target_week = fantasy_week_number(
            moment, season_week1_tuesday=season_week1_tuesday_from_env()
        )
    if target_week < 1 or target_week > 18:
        raise ValueError(f"invalid week {target_week}")

    stats_rows, _ = _resolve_stats_rows(season, dataset)
    usage_unavailable = len(stats_rows) == 0
    snap_rows, _ = _resolve_snap_rows(season)
    snap_filtered = len(snap_rows) > 0
    snap_index = build_snap_pct_index(snap_rows, season=season) if snap_filtered else None

    rated_through, rating_weeks, softness = build_defense_epa_softness_index(
        position=position,
        window=window,
        games=dataset.games,
        stats_rows=stats_rows,
        teams=dataset.teams,
        season=season,
    )
    usage = build_usage_index(
        stats_rows,
        position=position,
        weeks=set(rating_weeks),
        season=season,
        snap_pct_index=snap_index,
        min_offense_snap_pct=DEFAULT_MIN_OFFENSE_SNAP_PCT,
    )
    lines = game_lines or []
    players = build_tier2_player_opportunity(
        position=position,
        usage_index=usage,
        defense_softness=softness,
        schedule=dataset.schedule,
        week=target_week,
        game_lines=lines,
        snap_filtered=snap_filtered,
    )

    join_stats: dict[str, int] | None = None
    overlay_error: str | None = None
    if league_id:
        try:
            espn_s2, swid, cred_season = espn_credentials_from_env()
            roster_season = season or cred_season
            if espn_http_json is not None:
                espn_s2 = espn_s2 or "test-espn-s2"
                swid = swid or "{00000000-0000-0000-0000-000000000000}"
            roster = fetch_league_roster(
                league_id=league_id,
                season=roster_season,
                espn_s2=espn_s2,
                swid=swid,
                http_json=espn_http_json,
            )
            players, join_stats = join_roster_opportunity(
                roster, players, position=position
            )
        except EspnRosterError as exc:
            logger.warning("SoS Tier2 ESPN roster join unavailable: %s", exc)
            players = []
            join_stats = {"matched": 0, "unmatched": 0, "skippedPosition": 0}
            overlay_error = "espn_unavailable"

    fetched_at = dataset.fetched_at or moment.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    body: dict[str, Any] = {
        "season": season,
        "position": position,
        "window": window,
        "week": target_week,
        "ratedThroughWeek": rated_through,
        "ratingWeeks": list(rating_weeks),
        "shrinkK": SHRINK_K,
        "softnessMetric": "epa_allowed",
        "minOffenseSnapPct": DEFAULT_MIN_OFFENSE_SNAP_PCT,
        "snapFiltered": snap_filtered,
        "gameScriptApplied": any(row.get("gameScriptApplied") for row in players),
        "fetchedAt": fetched_at,
        "source": source,
        "stale": stale,
        "players": players,
    }
    body.update(league_meta)
    if join_stats is not None:
        body["joinStats"] = join_stats
    if overlay_error:
        body["overlayError"] = overlay_error
    if usage_unavailable:
        body["usageUnavailable"] = True
    return body
