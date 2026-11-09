"""Assemble Workbook matchups / feeder / explain API payloads.

Mirrors `draft_api/sos/service.py`: a 6h TTL cache in front of the live
nflverse loader, a packaged-snapshot fallback (`stale: true`) when nflverse
is unreachable, and test hooks (`set_workbook_dataset_override`,
`clear_workbook_cache`) so callers (and FastAPI routes in Task 8) never hit
the network in tests.

Net math, DSR, PROE, and positional OFF/DEF averaging all live in
`workbook.calculate` / `workbook.fantasy` (pure, already tested). This module
is the thin assembly layer: resolve the dataset, resolve the stat window,
sum raw positional rates into per-game metrics, and net them per the
`workbook/README.md` SSOT.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from draft_api.implied_totals import GameLine, implied_team_totals
from draft_api.odds.cache import TtlCache
from draft_api.workbook.calculate import (
    DriveOutcome,
    RateSide,
    StatWeekMode,
    build_game_environment_net,
    build_positional_net,
    build_team_env_rates,
    drive_success_rate,
    is_main_slate,
    mean_net,
    resolve_stat_weeks,
)
from draft_api.espn_available_dst import (
    EspnAvailableError,
    HttpJsonGetter,
    espn_credentials_from_env,
)
from draft_api.espn_leagues import get_league
from draft_api.espn_roster import EspnRosterError, load_espn_overlay_players
from draft_api.workbook.espn_overlay import build_highlights, highlights_to_json
from draft_api.workbook.fantasy import Scoring, passing_points, receiving_points, rushing_points
from draft_api.workbook.identity import normalize_team
from draft_api.workbook.injuries import (
    InjuriesFetchError,
    fetch_week_injuries,
    row_to_json as injury_row_to_json,
)
from draft_api.workbook.matrices import MatrixGroup, MatrixMetric, build_matrix_payload
from draft_api.workbook.nflverse import (
    HttpGetter,
    PositionalWeekRate,
    WorkbookDataset,
    WorkbookNflverseError,
    load_workbook_dataset,
)
from draft_api.workbook.pace import build_pace_table, row_to_json as pace_row_to_json
from draft_api.workbook.top import build_top_table, slice_to_json as top_slice_to_json
from draft_api.workbook.snapshot import SnapshotError, read_packaged_snapshot

logger = logging.getLogger("fantasy_draft_api.workbook")

DEFAULT_SEASON = 2026

# Main-slate kickoffs are classified in America/Chicago per `is_main_slate`'s
# contract (Sunday, before 7pm local) — see Task 4 / `calculate.is_main_slate`.
_CHICAGO_TZ = ZoneInfo("America/Chicago")

ATTRIBUTION = (
    "Computed by FantasyDraftTool from nflverse + odds. Out/Slot roles from ESPN "
    "Mike Clay WR/CB cheat sheet (role-based); stats from nflverse. Methodology "
    "inspired by Majesstik/OWS Workbook; not their sheet."
)

# Out/Slot WR uses Clay role aggregation + nflverse weekly stats. Rather than
# show a Net built on zero samples, require at least this many team-weeks of OFF
# *and* DEF data in the window — otherwise return null + reason.
_MIN_CLAY_SAMPLE_GAMES = 1
_CLAY_INSUFFICIENT_REASON = "clay_unavailable"

_SCORINGS: tuple[str, ...] = ("ppr", "half_ppr")
_WINDOWS: tuple[str, ...] = ("l4", "season", "custom")
_SLATES: tuple[str, ...] = ("main", "all")
_FEEDER_GROUPS: tuple[str, ...] = ("dsr", "qb", "wr", "te", "rb", "targets", "yards", "tds")
_EXPLAIN_METRICS: tuple[str, ...] = (
    "dsr",
    "qb_fp",
    "wr_fp",
    "te_fp",
    "rb_fp",
    "out_wr_fp",
    "slot_wr_fp",
)
_MATRIX_GROUPS: tuple[str, ...] = ("qb", "wr", "te", "rb", "dsr")
_MATRIX_METRICS: tuple[str, ...] = (
    "fp_per_game",
    "targets_per_game",
    "yards_per_game",
    "tds_per_game",
    "dsr",
)

# Feeder group -> positional_off/positional_def bucket key.
_FEEDER_POSITIONAL_GROUP: dict[str, str] = {"qb": "qb", "wr": "all_wr", "te": "te", "rb": "rb"}
# Explain metric -> positional_off/positional_def bucket key.
_EXPLAIN_POSITIONAL_GROUP: dict[str, str] = {
    "qb_fp": "qb",
    "wr_fp": "all_wr",
    "te_fp": "te",
    "rb_fp": "rb",
    "out_wr_fp": "out_wr",
    "slot_wr_fp": "slot_wr",
}
# Receiving volume field backing each `targets|yards|tds` feeder group.
_FEEDER_VOLUME_FIELDS: dict[str, str] = {
    "targets": "targets",
    "yards": "rec_yards",
    "tds": "rec_tds",
}
# Positional groups whose Net block uses a single `fpG`/`fpGTot` headline key.
_HEADLINE_KEY: dict[str, str] = {"qb": "fpGTot", "rb": "fpGTot"}

_dataset_cache: TtlCache[WorkbookDataset] = TtlCache(ttl_seconds=6 * 3600)
_http_get_override: HttpGetter | None = None
_dataset_override: WorkbookDataset | None = None


class WorkbookServiceError(ValueError):
    """Raised for invalid matchups/feeder/explain parameters (maps to HTTP 400)."""


def set_workbook_http_get(http_get: HttpGetter | None) -> None:
    """Test hook: override nflverse downloader (None restores default)."""
    global _http_get_override
    _http_get_override = http_get
    _dataset_cache.clear()


def set_workbook_dataset_override(dataset: WorkbookDataset | None) -> None:
    """Test hook: inject a fully built dataset (skips download + snapshot)."""
    global _dataset_override
    _dataset_override = dataset
    _dataset_cache.clear()


def set_workbook_cache_ttl(seconds: float) -> None:
    """Test hook: rebuild cache with a custom TTL."""
    global _dataset_cache
    _dataset_cache = TtlCache(ttl_seconds=seconds)


def clear_workbook_cache() -> None:
    _dataset_cache.clear()


def resolve_dataset(
    season: int, *, now: datetime | None = None
) -> tuple[WorkbookDataset, str, bool]:
    """Return (dataset, source, stale). Prefer live nflverse; fall back to snapshot."""
    if _dataset_override is not None:
        return _dataset_override, "fixture", False

    cached = _dataset_cache.get()
    if cached is not None and cached.season == season:
        return cached, "nflverse", False

    previous_clay_roles: dict[str, str] | None = None
    try:
        previous_clay_roles = read_packaged_snapshot(season).clay_roles or None
    except SnapshotError:
        previous_clay_roles = None

    try:
        dataset = load_workbook_dataset(
            season,
            http_get=_http_get_override,
            now=now,
            previous_clay_roles=previous_clay_roles,
        )
        _dataset_cache.set(dataset)
        return dataset, "nflverse", False
    except WorkbookNflverseError as exc:
        logger.warning("nflverse Workbook fetch failed; using snapshot: %s", exc)
        try:
            snapshot = read_packaged_snapshot(season)
            return snapshot, "snapshot", True
        except SnapshotError as snap_exc:
            raise WorkbookNflverseError(
                f"nflverse unavailable ({exc}) and snapshot missing ({snap_exc})"
            ) from snap_exc


def _validate_choice(value: str, allowed: tuple[str, ...], *, field_name: str) -> None:
    if value not in allowed:
        joined = ", ".join(allowed)
        raise WorkbookServiceError(f"invalid {field_name} {value!r} (expected one of {joined})")


def _rated_through_week(week: int) -> int:
    return max(0, min(week - 1, 18))


def _resolve_weeks(
    *,
    window: str,
    rated_through_week: int,
    custom_start_week: int | None,
    custom_end_week: int | None,
) -> set[int]:
    return resolve_stat_weeks(
        mode=cast(StatWeekMode, window),
        rated_through_week=rated_through_week,
        custom_start=custom_start_week,
        custom_end=custom_end_week,
    )


def _fetched_at(dataset: WorkbookDataset, moment: datetime) -> str:
    return dataset.fetched_at or moment.astimezone(UTC).isoformat().replace(
        "+00:00", "Z"
    )


def _is_main_slate_kickoff(kickoff: str | None) -> bool:
    """False for an unknown kickoff (never promoted into the `main` slate)."""
    if not kickoff:
        return False
    try:
        moment = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except ValueError:
        return False
    local = moment.astimezone(_CHICAGO_TZ)
    return is_main_slate(weekday_local=local.weekday(), kickoff_hour_local=local.hour)


# --- Drive success rate (offense + schedule-derived defense allowed) ------


def _defense_allowed_dsr(dataset: WorkbookDataset, *, team: str, weeks: set[int]) -> float | None:
    """Share of opponents' drives that succeeded against `team`'s defense.

    `DriveOutcome` only tags the offensive team per drive (see
    `workbook.calculate.DriveOutcome`), so the defense-allowed leg is derived
    by looking up each week's opponent in the season schedule and pooling
    that opponent's drives for the week.
    """
    matched: list[DriveOutcome] = []
    for week in weeks:
        opponent = (dataset.schedule.get(week) or {}).get(team)
        if not opponent:
            continue
        matched.extend(d for d in dataset.drives if d.team == opponent and d.week == week)
    if not matched:
        return None
    return sum(1 for d in matched if d.success) / len(matched)


def _net_dsr_pair(
    dataset: WorkbookDataset, *, team: str, opponent: str, weeks: set[int]
) -> tuple[float | None, float | None]:
    """Return (team_net_dsr, opponent_net_dsr) for `build_game_environment_net`."""
    team_off = drive_success_rate(dataset.drives, team=team, weeks=weeks)
    opp_def_allowed = _defense_allowed_dsr(dataset, team=opponent, weeks=weeks)
    team_net = mean_net(team_off, opp_def_allowed)

    opp_off = drive_success_rate(dataset.drives, team=opponent, weeks=weeks)
    team_def_allowed = _defense_allowed_dsr(dataset, team=team, weeks=weeks)
    opp_net = mean_net(opp_off, team_def_allowed)
    return team_net, opp_net


# --- Positional OFF/DEF rate sums ------------------------------------------


def _sum_group_rates(
    dataset: WorkbookDataset, *, side: RateSide, group: str, team: str, weeks: set[int]
) -> tuple[PositionalWeekRate | None, int]:
    """Sum one team's raw positional counters across the window; also games played."""
    bucket = dataset.positional_off if side == "off" else dataset.positional_def
    matched = [rate for (t, w), rate in bucket.get(group, {}).items() if t == team and w in weeks]
    games = len(matched)
    if games == 0:
        return None, 0
    summed = PositionalWeekRate(
        targets=sum(r.targets or 0.0 for r in matched),
        receptions=sum(r.receptions or 0.0 for r in matched),
        rec_yards=sum(r.rec_yards or 0.0 for r in matched),
        rec_tds=sum(r.rec_tds or 0.0 for r in matched),
        rush_att=sum(r.rush_att or 0.0 for r in matched),
        rush_yards=sum(r.rush_yards or 0.0 for r in matched),
        rush_tds=sum(r.rush_tds or 0.0 for r in matched),
        pass_yards=sum(r.pass_yards or 0.0 for r in matched),
        pass_tds=sum(r.pass_tds or 0.0 for r in matched),
        fantasy_points=sum(r.fantasy_points or 0.0 for r in matched),
    )
    return summed, games


def _team_total_targets(
    dataset: WorkbookDataset, *, side: RateSide, team: str, weeks: set[int]
) -> float:
    """Total team targets across WR + TE + RB for the window (tarPct denominator)."""
    bucket = dataset.positional_off if side == "off" else dataset.positional_def
    total = 0.0
    for group in ("all_wr", "te", "rb"):
        for (t, w), rate in bucket.get(group, {}).items():
            if t == team and w in weeks and rate.targets is not None:
                total += rate.targets
    return total


def _rate_metrics(
    summed: PositionalWeekRate | None,
    games: int,
    *,
    group: str,
    scoring: Scoring,
    total_targets: float,
) -> dict[str, float | None]:
    """Per-game metrics for one OFF or DEF leg; `{}` when there is no sample."""
    if summed is None or games == 0:
        return {}

    if group == "qb":
        pass_pts = passing_points(yards=summed.pass_yards or 0.0, tds=summed.pass_tds or 0.0)
        run_pts = rushing_points(yards=summed.rush_yards or 0.0, tds=summed.rush_tds or 0.0)
        return {
            "fpGTot": (pass_pts + run_pts) / games,
            "fpGPass": pass_pts / games,
            "fpGRun": run_pts / games,
            "ydsG": ((summed.pass_yards or 0.0) + (summed.rush_yards or 0.0)) / games,
            "passTdG": (summed.pass_tds or 0.0) / games,
        }

    if group == "rb":
        rec_pts = receiving_points(
            receptions=summed.receptions or 0.0,
            yards=summed.rec_yards or 0.0,
            tds=summed.rec_tds or 0.0,
            scoring=scoring,
        )
        run_pts = rushing_points(yards=summed.rush_yards or 0.0, tds=summed.rush_tds or 0.0)
        targets = summed.targets or 0.0
        return {
            "fpGTot": (rec_pts + run_pts) / games,
            "fpRec": rec_pts / games,
            "fpRun": run_pts / games,
            "tarG": targets / games,
            "tarPct": (targets / total_targets) if total_targets else None,
            "recYdG": (summed.rec_yards or 0.0) / games,
            "recTdG": (summed.rec_tds or 0.0) / games,
            "attG": (summed.rush_att or 0.0) / games,
            "rushYdG": (summed.rush_yards or 0.0) / games,
            "rushTdG": (summed.rush_tds or 0.0) / games,
        }

    # Receiving-only groups: all_wr, out_wr, slot_wr, te.
    rec_pts = receiving_points(
        receptions=summed.receptions or 0.0,
        yards=summed.rec_yards or 0.0,
        tds=summed.rec_tds or 0.0,
        scoring=scoring,
    )
    targets = summed.targets or 0.0
    return {
        "fpG": rec_pts / games,
        "tarG": targets / games,
        "tarPct": (targets / total_targets) if total_targets else None,
        "ydG": (summed.rec_yards or 0.0) / games,
        "tdG": (summed.rec_tds or 0.0) / games,
    }


def _positional_block(
    dataset: WorkbookDataset,
    *,
    group: str,
    team: str,
    opponent: str,
    weeks: set[int],
    scoring: Scoring,
    clay_role_gated: bool = False,
) -> dict[str, Any]:
    off_summed, off_games = _sum_group_rates(
        dataset, side="off", group=group, team=team, weeks=weeks
    )
    def_summed, def_games = _sum_group_rates(
        dataset, side="def", group=group, team=opponent, weeks=weeks
    )

    if clay_role_gated and (
        off_games < _MIN_CLAY_SAMPLE_GAMES or def_games < _MIN_CLAY_SAMPLE_GAMES
    ):
        return {"fpG": None, "reason": _CLAY_INSUFFICIENT_REASON}

    off_total_targets = _team_total_targets(dataset, side="off", team=team, weeks=weeks)
    def_total_targets = _team_total_targets(dataset, side="def", team=opponent, weeks=weeks)

    off_metrics = _rate_metrics(
        off_summed, off_games, group=group, scoring=scoring, total_targets=off_total_targets
    )
    def_metrics = _rate_metrics(
        def_summed, def_games, group=group, scoring=scoring, total_targets=def_total_targets
    )
    return build_positional_net(off_metrics, def_metrics)


# --- Vegas implied points (optional) ---------------------------------------


def _index_odds_games(odds_games: Sequence[GameLine]) -> dict[tuple[str, str], GameLine]:
    return {(normalize_team(g.home_team), normalize_team(g.away_team)): g for g in odds_games}


def _implied_points_for(
    odds_by_pair: dict[tuple[str, str], GameLine],
    *,
    home: str,
    away: str,
    side: Literal["home", "away"],
) -> float | None:
    game = odds_by_pair.get((home, away))
    if game is None:
        return None
    favorite_implied, underdog_implied = implied_team_totals(total=game.total, spread=game.spread)
    favorite = normalize_team(game.favorite_team)
    if favorite == home:
        home_implied, away_implied = favorite_implied, underdog_implied
    elif favorite == away:
        home_implied, away_implied = underdog_implied, favorite_implied
    else:
        return None
    return home_implied if side == "home" else away_implied


# --- Matchups ----------------------------------------------------------------


def _build_team_row(
    dataset: WorkbookDataset,
    *,
    team: str,
    opponent: str,
    home_away: Literal["home", "away"],
    weeks: set[int],
    scoring: Scoring,
    implied_points: float | None,
) -> dict[str, Any]:
    team_net_dsr, opp_net_dsr = _net_dsr_pair(dataset, team=team, opponent=opponent, weeks=weeks)
    team_off_env = build_team_env_rates(dataset.team_env_off, team=team, side="off", weeks=weeks)
    opp_def_env = build_team_env_rates(dataset.team_env_def, team=opponent, side="def", weeks=weeks)

    game_environment = build_game_environment_net(
        team_off=team_off_env,
        opp_def=opp_def_env,
        team_net_dsr=team_net_dsr,
        opp_net_dsr=opp_net_dsr,
        implied_points=implied_points,
    )

    return {
        "team": team,
        "homeAway": home_away,
        "opponent": opponent,
        "gameEnvironment": game_environment,
        "qb": _positional_block(
            dataset, group="qb", team=team, opponent=opponent, weeks=weeks, scoring=scoring
        ),
        "allWr": _positional_block(
            dataset, group="all_wr", team=team, opponent=opponent, weeks=weeks, scoring=scoring
        ),
        "outWr": _positional_block(
            dataset,
            group="out_wr",
            team=team,
            opponent=opponent,
            weeks=weeks,
            scoring=scoring,
            clay_role_gated=True,
        ),
        "slotWr": _positional_block(
            dataset,
            group="slot_wr",
            team=team,
            opponent=opponent,
            weeks=weeks,
            scoring=scoring,
            clay_role_gated=True,
        ),
        "te": _positional_block(
            dataset, group="te", team=team, opponent=opponent, weeks=weeks, scoring=scoring
        ),
        "rb": _positional_block(
            dataset, group="rb", team=team, opponent=opponent, weeks=weeks, scoring=scoring
        ),
    }


def _merge_espn_overlay(
    payload: dict[str, Any],
    *,
    league_id: str,
    season: int,
    owner: str | None,
    owner_team_id: int | None,
    include_fa: bool,
    espn_http_json: HttpJsonGetter | None,
) -> dict[str, Any]:
    get_league(league_id)
    try:
        espn_s2, swid, _ = espn_credentials_from_env()
        if espn_http_json is not None:
            espn_s2 = espn_s2 or "test-espn-s2"
            swid = swid or "{00000000-0000-0000-0000-000000000000}"
        elif not espn_s2 or not swid:
            raise EspnRosterError("ESPN credentials are not configured")
        roster, free_agents, resolved_owner = load_espn_overlay_players(
            league_id=league_id,
            season=season,
            espn_s2=espn_s2,
            swid=swid,
            owner=owner,
            owner_team_id=owner_team_id,
            include_fa=include_fa,
            http_json=espn_http_json,
        )
        highlights, join_stats = build_highlights(
            games=list(payload.get("games") or []),
            roster=roster,
            free_agents=free_agents,
            owner_team_id=resolved_owner,
            include_fa=include_fa,
        )
        payload.update(highlights_to_json(highlights, join_stats))
    except (EspnRosterError, EspnAvailableError) as exc:
        logger.warning("Workbook ESPN overlay unavailable: %s", exc)
        payload["highlights"] = []
        payload["joinStats"] = {
            "matched": 0,
            "unmatched_team": 0,
            "unmatched_name_only": 0,
        }
        payload["overlayError"] = "espn_unavailable"
    return payload


def build_matchups_response(
    *,
    week: int,
    window: str,
    scoring: str,
    slate: str,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
    odds_games: Sequence[GameLine] | None = None,
    league_id: str | None = None,
    owner: str | None = None,
    owner_team_id: int | None = None,
    include_fa: bool = True,
    espn_http_json: HttpJsonGetter | None = None,
) -> dict[str, Any]:
    """Build the Workbook Net Matchups board for one week.

    `odds_games` is optional (Task 8 wires the real `OddsProvider`): when
    omitted, every row's `vegasImpliedPoints` is `null` and the rest of the
    board still renders — the board must never fail because odds are down.
    """
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    _validate_choice(window, _WINDOWS, field_name="window")
    _validate_choice(scoring, _SCORINGS, field_name="scoring")
    _validate_choice(slate, _SLATES, field_name="slate")
    scoring_literal = cast(Scoring, scoring)

    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)

    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )
    odds_by_pair = _index_odds_games(odds_games or [])

    games_payload: list[dict[str, Any]] = []
    week_games = sorted(
        (g for g in dataset.games if g.week == week), key=lambda g: (g.kickoff or "", g.home)
    )
    for game in week_games:
        main_slate = _is_main_slate_kickoff(game.kickoff)
        if slate == "main" and not main_slate:
            continue
        rows = [
            _build_team_row(
                dataset,
                team=game.home,
                opponent=game.away,
                home_away="home",
                weeks=weeks,
                scoring=scoring_literal,
                implied_points=_implied_points_for(
                    odds_by_pair, home=game.home, away=game.away, side="home"
                ),
            ),
            _build_team_row(
                dataset,
                team=game.away,
                opponent=game.home,
                home_away="away",
                weeks=weeks,
                scoring=scoring_literal,
                implied_points=_implied_points_for(
                    odds_by_pair, home=game.home, away=game.away, side="away"
                ),
            ),
        ]
        games_payload.append(
            {
                "away": game.away,
                "home": game.home,
                "kickoff": game.kickoff,
                "mainSlate": main_slate,
                "rows": rows,
            }
        )

    payload = {
        "season": dataset.season,
        "week": week,
        "window": window,
        "scoring": scoring,
        "slate": slate,
        "ratedThroughWeek": rated_through_week,
        "fetchedAt": _fetched_at(dataset, moment),
        "source": source,
        "stale": stale,
        "attribution": ATTRIBUTION,
        "games": games_payload,
    }
    if league_id:
        return _merge_espn_overlay(
            payload,
            league_id=league_id,
            season=season,
            owner=owner,
            owner_team_id=owner_team_id,
            include_fa=include_fa,
            espn_http_json=espn_http_json,
        )
    return payload


# --- Feeders -----------------------------------------------------------------


def _volume_sum(
    dataset: WorkbookDataset, *, side: RateSide, team: str, weeks: set[int], field_name: str
) -> tuple[float, int]:
    bucket = dataset.positional_off if side == "off" else dataset.positional_def
    total = 0.0
    games_with_data: set[int] = set()
    for group in ("all_wr", "te", "rb"):
        for (t, w), rate in bucket.get(group, {}).items():
            if t != team or w not in weeks:
                continue
            value = getattr(rate, field_name)
            if value is not None:
                total += value
            games_with_data.add(w)
    return total, len(games_with_data)


def _feeder_row(
    dataset: WorkbookDataset, *, group: str, team: str, weeks: set[int], scoring: Scoring
) -> dict[str, Any]:
    if group == "dsr":
        off = drive_success_rate(dataset.drives, team=team, weeks=weeks)
        def_allowed = _defense_allowed_dsr(dataset, team=team, weeks=weeks)
        return {"team": team, "off": off, "def": def_allowed, "net": mean_net(off, def_allowed)}

    if group in _FEEDER_POSITIONAL_GROUP:
        pos_group = _FEEDER_POSITIONAL_GROUP[group]
        off_summed, off_games = _sum_group_rates(
            dataset, side="off", group=pos_group, team=team, weeks=weeks
        )
        def_summed, def_games = _sum_group_rates(
            dataset, side="def", group=pos_group, team=team, weeks=weeks
        )
        off_total_targets = _team_total_targets(dataset, side="off", team=team, weeks=weeks)
        def_total_targets = _team_total_targets(dataset, side="def", team=team, weeks=weeks)
        off_metrics = _rate_metrics(
            off_summed, off_games, group=pos_group, scoring=scoring, total_targets=off_total_targets
        )
        def_metrics = _rate_metrics(
            def_summed, def_games, group=pos_group, scoring=scoring, total_targets=def_total_targets
        )
        headline = _HEADLINE_KEY.get(pos_group, "fpG")
        off_value = off_metrics.get(headline)
        def_value = def_metrics.get(headline)
        return {
            "team": team,
            "off": off_value,
            "def": def_value,
            "net": mean_net(off_value, def_value),
        }

    # Volume feeders: targets / yards / tds per game, pooled across WR+TE+RB.
    field_name = _FEEDER_VOLUME_FIELDS[group]
    off_total, off_games = _volume_sum(
        dataset, side="off", team=team, weeks=weeks, field_name=field_name
    )
    def_total, def_games = _volume_sum(
        dataset, side="def", team=team, weeks=weeks, field_name=field_name
    )
    off_rate = (off_total / off_games) if off_games else None
    def_rate = (def_total / def_games) if def_games else None
    return {"team": team, "off": off_rate, "def": def_rate, "net": mean_net(off_rate, def_rate)}


def build_feeder_response(
    *,
    group: str,
    window: str,
    scoring: str,
    week: int,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    """Build one feeder table (OFF/DEF/Net per team) for `group`."""
    _validate_choice(group, _FEEDER_GROUPS, field_name="group")
    _validate_choice(window, _WINDOWS, field_name="window")
    _validate_choice(scoring, _SCORINGS, field_name="scoring")
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    scoring_literal = cast(Scoring, scoring)

    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)
    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )

    teams = [
        _feeder_row(dataset, group=group, team=team, weeks=weeks, scoring=scoring_literal)
        for team in sorted(dataset.teams)
    ]

    return {
        "season": dataset.season,
        "week": week,
        "window": window,
        "scoring": scoring,
        "group": group,
        "ratedThroughWeek": rated_through_week,
        "fetchedAt": _fetched_at(dataset, moment),
        "source": source,
        "stale": stale,
        "attribution": ATTRIBUTION,
        "teams": teams,
    }


# --- Explain -----------------------------------------------------------------


def _explain_metric(
    dataset: WorkbookDataset,
    *,
    team: str,
    opponent: str | None,
    metric: str,
    weeks: set[int],
    scoring: Scoring,
) -> tuple[float | None, float | None, float | None]:
    if metric == "dsr":
        off = drive_success_rate(dataset.drives, team=team, weeks=weeks)
        def_allowed = (
            _defense_allowed_dsr(dataset, team=opponent, weeks=weeks) if opponent else None
        )
        return off, def_allowed, mean_net(off, def_allowed)

    group = _EXPLAIN_POSITIONAL_GROUP[metric]
    headline = _HEADLINE_KEY.get(group, "fpG")

    off_summed, off_games = _sum_group_rates(
        dataset, side="off", group=group, team=team, weeks=weeks
    )
    off_total_targets = _team_total_targets(dataset, side="off", team=team, weeks=weeks)
    off_metrics = _rate_metrics(
        off_summed, off_games, group=group, scoring=scoring, total_targets=off_total_targets
    )
    off_value = off_metrics.get(headline)

    clay_role_gated = group in ("out_wr", "slot_wr")
    if clay_role_gated and off_games < _MIN_CLAY_SAMPLE_GAMES:
        return None, None, None

    if opponent is None:
        return off_value, None, None

    def_summed, def_games = _sum_group_rates(
        dataset, side="def", group=group, team=opponent, weeks=weeks
    )
    if clay_role_gated and def_games < _MIN_CLAY_SAMPLE_GAMES:
        return None, None, None

    def_total_targets = _team_total_targets(dataset, side="def", team=opponent, weeks=weeks)
    def_metrics = _rate_metrics(
        def_summed, def_games, group=group, scoring=scoring, total_targets=def_total_targets
    )
    def_value = def_metrics.get(headline)
    return off_value, def_value, mean_net(off_value, def_value)


def build_explain_response(
    *,
    team: str,
    week: int,
    metric: str,
    window: str,
    scoring: str,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    """Build the OFF/DEF/Net breakdown behind one matchups-board cell."""
    _validate_choice(metric, _EXPLAIN_METRICS, field_name="metric")
    _validate_choice(window, _WINDOWS, field_name="window")
    _validate_choice(scoring, _SCORINGS, field_name="scoring")
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    scoring_literal = cast(Scoring, scoring)

    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)

    team_norm = normalize_team(team)
    if team_norm not in dataset.teams:
        raise WorkbookServiceError(f"unknown team {team!r}")
    opponent = (dataset.schedule.get(week) or {}).get(team_norm)

    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )

    off_value, def_value, net_value = _explain_metric(
        dataset,
        team=team_norm,
        opponent=opponent,
        metric=metric,
        weeks=weeks,
        scoring=scoring_literal,
    )

    return {
        "season": dataset.season,
        "week": week,
        "team": team_norm,
        "opponent": opponent,
        "metric": metric,
        "window": window,
        "scoring": scoring,
        "ratedThroughWeek": rated_through_week,
        "fetchedAt": _fetched_at(dataset, moment),
        "source": source,
        "stale": stale,
        "attribution": ATTRIBUTION,
        "off": off_value,
        "def": def_value,
        "net": net_value,
    }


# --- P2 tabs: TOP / Pace / Injuries / Matrices --------------------------------


def _p2_workbook_meta(
    dataset: WorkbookDataset,
    *,
    week: int,
    window: str,
    moment: datetime,
    source: str,
    stale: bool,
    **extra: Any,
) -> dict[str, Any]:
    rated_through_week = _rated_through_week(week)
    return {
        "season": dataset.season,
        "week": week,
        "window": window,
        "ratedThroughWeek": rated_through_week,
        "fetchedAt": _fetched_at(dataset, moment),
        "source": source,
        "stale": stale,
        "attribution": ATTRIBUTION,
        **extra,
    }


def build_top_response(
    *,
    week: int,
    window: str,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    _validate_choice(window, _WINDOWS, field_name="window")

    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)
    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )
    teams = build_top_table(dataset, weeks=weeks)
    method = teams[0].method if teams else "plays_share_proxy"
    if any(row.method == "pbp_drive" for row in teams):
        method = "pbp_drive"
    payload = _p2_workbook_meta(
        dataset, week=week, window=window, moment=moment, source=source, stale=stale
    )
    payload["method"] = method
    payload["teams"] = [top_slice_to_json(row) for row in teams]
    return payload


def build_pace_response(
    *,
    week: int,
    window: str,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    _validate_choice(window, _WINDOWS, field_name="window")

    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)
    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )
    teams = build_pace_table(dataset, weeks=weeks)
    payload = _p2_workbook_meta(
        dataset, week=week, window=window, moment=moment, source=source, stale=stale
    )
    payload["teams"] = [pace_row_to_json(row) for row in teams]
    return payload


def build_injuries_response(
    *,
    week: int,
    season: int = DEFAULT_SEASON,
    league_id: str | None = None,
    now: datetime | None = None,
    espn_http_json: HttpJsonGetter | None = None,
) -> dict[str, Any]:
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    if not league_id:
        raise WorkbookServiceError("leagueId is required for Workbook injuries")

    moment = now or datetime.now(UTC)
    get_league(league_id)
    warnings: list[str] = []
    injuries: list[dict[str, Any]] = []
    try:
        espn_s2, swid, _ = espn_credentials_from_env()
        if espn_http_json is not None:
            espn_s2 = espn_s2 or "test-espn-s2"
            swid = swid or "{00000000-0000-0000-0000-000000000000}"
        elif not espn_s2 or not swid:
            raise InjuriesFetchError("ESPN credentials are not configured")
        rows = fetch_week_injuries(
            league_id=league_id,
            season=season,
            week=week,
            espn_s2=espn_s2,
            swid=swid,
            http_json=espn_http_json,
        )
        injuries = [injury_row_to_json(row) for row in rows]
    except (InjuriesFetchError, EspnRosterError, EspnAvailableError) as exc:
        logger.warning("Workbook injuries unavailable: %s", exc)
        warnings.append("injuries_unavailable")

    return {
        "season": season,
        "week": week,
        "fetchedAt": moment.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "source": "espn",
        "stale": False,
        "injuries": injuries,
        "warnings": warnings,
    }


def build_matrix_response(
    *,
    group: str,
    metric: str,
    week: int,
    window: str,
    scoring: str,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    _validate_choice(group, _MATRIX_GROUPS, field_name="group")
    _validate_choice(metric, _MATRIX_METRICS, field_name="metric")
    _validate_choice(window, _WINDOWS, field_name="window")
    _validate_choice(scoring, _SCORINGS, field_name="scoring")
    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    if group != "dsr" and metric == "dsr":
        raise WorkbookServiceError("metric dsr requires group dsr")
    if group == "dsr" and metric != "dsr":
        raise WorkbookServiceError("dsr group requires metric dsr")

    scoring_literal = cast(Scoring, scoring)
    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)
    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )
    matrix = build_matrix_payload(
        dataset,
        group=cast(MatrixGroup, group),
        metric=cast(MatrixMetric, metric),
        weeks=weeks,
        scoring=scoring_literal,
    )
    payload = _p2_workbook_meta(
        dataset,
        week=week,
        window=window,
        moment=moment,
        source=source,
        stale=stale,
        scoring=scoring,
        group=group,
        metric=metric,
    )
    payload["teams"] = matrix["teams"]
    return payload


# --- P3: DFS pool rank + OL/DL proxy ----------------------------------------


def build_pool_rank_response(
    *,
    week: int,
    window: str,
    scoring: str | None,
    players: Sequence[dict[str, Any]],
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    """Rank a pasted DFS pool using Workbook Net matchup metrics."""
    from draft_api.workbook.pool import (
        MAX_POOL_PLAYERS,
        PoolPlayerInput,
        rank_pool,
        row_to_json,
    )

    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    _validate_choice(window, _WINDOWS, field_name="window")
    scoring_value = scoring or "half_ppr"
    _validate_choice(scoring_value, _SCORINGS, field_name="scoring")
    if len(players) > MAX_POOL_PLAYERS:
        raise WorkbookServiceError(f"pool exceeds {MAX_POOL_PLAYERS} players")

    scoring_literal = cast(Scoring, scoring_value)
    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)
    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )

    inputs = [
        PoolPlayerInput(
            name=str(item.get("name") or ""),
            team=str(item.get("team") or ""),
            salary=int(item.get("salary") or 0),
            position=str(item.get("position") or ""),
            opponent=(
                str(item["opponent"]) if item.get("opponent") is not None else None
            ),
        )
        for item in players
    ]
    try:
        ranked = rank_pool(
            inputs,
            dataset=dataset,
            week=week,
            weeks=weeks,
            scoring=scoring_literal,
        )
    except ValueError as exc:
        raise WorkbookServiceError(str(exc)) from exc

    payload = _p2_workbook_meta(
        dataset,
        week=week,
        window=window,
        moment=moment,
        source=source,
        stale=stale,
        scoring=scoring_value,
    )
    payload["players"] = [row_to_json(row) for row in ranked]
    return payload


def build_oldl_response(
    *,
    week: int,
    window: str,
    season: int = DEFAULT_SEASON,
    now: datetime | None = None,
    custom_start_week: int | None = None,
    custom_end_week: int | None = None,
) -> dict[str, Any]:
    """Build OL/DL proxy tab for one NFL week."""
    from draft_api.workbook.oldl import (
        OLDL_DISCLAIMER,
        build_oldl_games,
        build_oldl_team_rows,
        row_to_json as oldl_row_to_json,
    )

    if week < 1 or week > 18:
        raise WorkbookServiceError(f"invalid week {week}")
    _validate_choice(window, _WINDOWS, field_name="window")

    moment = now or datetime.now(UTC)
    dataset, source, stale = resolve_dataset(season, now=moment)
    rated_through_week = _rated_through_week(week)
    weeks = _resolve_weeks(
        window=window,
        rated_through_week=rated_through_week,
        custom_start_week=custom_start_week,
        custom_end_week=custom_end_week,
    )
    team_rows_list = build_oldl_team_rows(dataset, weeks=weeks)
    team_rows = {row.team: row for row in team_rows_list}
    payload = _p2_workbook_meta(
        dataset,
        week=week,
        window=window,
        moment=moment,
        source=source,
        stale=stale,
    )
    payload["disclaimer"] = OLDL_DISCLAIMER
    payload["teams"] = [oldl_row_to_json(row) for row in team_rows_list]
    payload["games"] = build_oldl_games(dataset, week=week, team_rows=team_rows)
    return payload
