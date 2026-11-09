"""Offline Tier 1 backtest harness (Spearman vs weekly fantasy points)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from draft_api.sos.calculate import (
    CompletedGame,
    Position,
    SosWindow,
    defensive_fpa,
    rank_defenses_shrunk,
    resolve_sos_window,
    softness_bucket,
)
from draft_api.sos.tier1 import DefenseSoftness, build_defense_softness_index, build_player_opportunity
from draft_api.sos.usage import build_usage_index

SoftnessBuilder = Callable[..., dict[str, DefenseSoftness]]


def _games_from_rows(rows: list[dict[str, Any]]) -> list[CompletedGame]:
    games: list[CompletedGame] = []
    for row in rows:
        points = row.get("points") or {}
        games.append(
            CompletedGame(
                week=int(row["week"]),
                offense=str(row["offense"]),
                defense=str(row["defense"]),
                points={
                    "QB": float(points.get("QB", 0.0)),
                    "RB": float(points.get("RB", 0.0)),
                    "WR": float(points.get("WR", 0.0)),
                    "TE": float(points.get("TE", 0.0)),
                    "DST": float(points.get("DST", 0.0)),
                },
            )
        )
    return games


def _tier1_softness(
    *,
    games: list[CompletedGame],
    position: Position,
    teams: list[str],
    window: SosWindow,
) -> dict[str, DefenseSoftness]:
    _, _, idx = build_defense_softness_index(
        position=position,
        window=window,
        games=games,
        teams=teams,
    )
    return idx


def _baseline_raw_fpa_softness(
    *,
    games: list[CompletedGame],
    position: Position,
    teams: list[str],
    window: SosWindow,
) -> dict[str, DefenseSoftness]:
    rated = max((g.week for g in games), default=0)
    weeks = resolve_sos_window(window, rated)
    window_games = [g for g in games if g.week in weeks]
    raw = defensive_fpa(window_games, position)
    ranks = rank_defenses_shrunk(raw, teams)
    out: dict[str, DefenseSoftness] = {}
    for defense, rank in ranks.items():
        softness, score = softness_bucket(rank)
        out[defense] = DefenseSoftness(
            defense=defense,
            rank=rank,
            softness=softness,
            softness_score=score,
        )
    return out


def spearman_rho(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation without scipy."""
    n = len(xs)
    if n != len(ys) or n < 2:
        return None

    def rank(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: (values[i], i))
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j + 2) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    den_x = sum((rx[i] - mean_x) ** 2 for i in range(n))
    den_y = sum((ry[i] - mean_y) ** 2 for i in range(n))
    if den_x <= 0.0 or den_y <= 0.0:
        return None
    return num / (den_x * den_y) ** 0.5


def _parse_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _collect_pairs(
    *,
    fixture: dict[str, Any],
    softness_builder: SoftnessBuilder,
) -> tuple[list[float], list[float]]:
    position: Position = fixture["position"]  # type: ignore[assignment]
    window: SosWindow = fixture.get("window", "season")  # type: ignore[assignment]
    season = int(fixture.get("season", 2026))
    teams: list[str] = list(fixture["teams"])
    schedule = {
        team: {int(w): opp for w, opp in weeks.items()}
        for team, weeks in fixture["schedule"].items()
    }
    all_games = _games_from_rows(fixture["games"])
    stats_rows = fixture.get("stats_rows") or []
    eval_weeks = [int(w) for w in fixture.get("evaluation_weeks") or []]

    opportunities: list[float] = []
    fps: list[float] = []

    for week in eval_weeks:
        prior_games = [g for g in all_games if g.week < week]
        if not prior_games:
            continue
        _, rating_weeks, _ = build_defense_softness_index(
            position=position,
            window=window,
            games=prior_games,
            teams=teams,
        )
        softness = softness_builder(
            games=prior_games,
            position=position,
            teams=teams,
            window=window,
        )
        usage = build_usage_index(
            stats_rows,
            position=position,
            weeks=set(rating_weeks),
            season=season,
        )
        tier_rows = build_player_opportunity(
            usage_index=usage,
            defense_softness=softness,
            schedule=schedule,
            week=week,
        )
        fp_by_name = {
            (row.get("player_display_name") or "").strip(): _parse_float(row.get("fantasy_points_ppr"))
            for row in stats_rows
            if int(row.get("week") or 0) == week
            and (row.get("position") or "").upper() == position
        }
        for row in tier_rows:
            opp = row.get("opportunity")
            fp = fp_by_name.get(row["name"])
            if opp is None or fp is None:
                continue
            opportunities.append(float(opp))
            fps.append(float(fp))

    return opportunities, fps


def run_tier1_backtest(fixture_path: str | Path) -> dict[str, Any]:
    """Load fixture JSON and compute Spearman for Tier 1 vs raw-FPA baseline."""
    path = Path(fixture_path)
    fixture = json.loads(path.read_text(encoding="utf-8"))

    tier_x, tier_y = _collect_pairs(fixture=fixture, softness_builder=_tier1_softness)
    base_x, base_y = _collect_pairs(fixture=fixture, softness_builder=_baseline_raw_fpa_softness)

    return {
        "fixture": path.name,
        "position": fixture.get("position"),
        "window": fixture.get("window", "season"),
        "n_observations": len(tier_x),
        "n_weeks": len(fixture.get("evaluation_weeks") or []),
        "spearman_rho": spearman_rho(tier_x, tier_y),
        "baseline_rho": spearman_rho(base_x, base_y),
    }
