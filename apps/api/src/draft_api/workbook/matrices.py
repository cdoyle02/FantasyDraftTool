"""Positional matrices — league-relative tertile tiers on feeder OFF/DEF/Net."""

from __future__ import annotations

import math
from typing import Literal, cast

from draft_api.workbook.fantasy import Scoring
from draft_api.workbook.nflverse import WorkbookDataset

Tertile = Literal["top", "mid", "bottom"]
MatrixGroup = Literal["qb", "wr", "te", "rb", "dsr"]
MatrixMetric = Literal[
    "fp_per_game",
    "targets_per_game",
    "yards_per_game",
    "tds_per_game",
    "dsr",
]

_TIER_COLOR: dict[Tertile, str] = {
    "top": "green",
    "mid": "neutral",
    "bottom": "red",
}

_GROUP_FEEDER: dict[MatrixGroup, str] = {
    "qb": "qb",
    "wr": "wr",
    "te": "te",
    "rb": "rb",
    "dsr": "dsr",
}

_VOLUME_METRICS: dict[str, str] = {
    "targets_per_game": "targets",
    "yards_per_game": "yards",
    "tds_per_game": "tds",
}


def assign_tertile(
    values: dict[str, float | None],
    *,
    higher_is_better: bool,
) -> dict[str, Tertile | None]:
    """Rank teams in three buckets: top/mid/bottom (``ceil(n/3)`` each for top and mid)."""
    pool = {team: value for team, value in values.items() if value is not None}
    n = len(pool)
    out: dict[str, Tertile | None] = {team: None for team in values}
    if n == 0:
        return out
    size = math.ceil(n / 3)
    ranked = sorted(pool.keys(), key=lambda team: pool[team], reverse=higher_is_better)
    for index, team in enumerate(ranked):
        if index < size:
            out[team] = "top"
        elif index < 2 * size:
            out[team] = "mid"
        else:
            out[team] = "bottom"
    return out


def _metric_higher_is_better(metric: MatrixMetric) -> bool:
    return True


def _cell(value: float | None, tier: Tertile | None) -> dict[str, object]:
    if value is None:
        return {"value": None, "tier": None, "tierColor": None}
    return {
        "value": value,
        "tier": tier,
        "tierColor": _TIER_COLOR[tier] if tier else None,
    }


def _feeder_group_for(group: MatrixGroup, metric: MatrixMetric) -> str:
    if metric in _VOLUME_METRICS:
        return _VOLUME_METRICS[metric]
    if group == "dsr" or metric == "dsr":
        return "dsr"
    return _GROUP_FEEDER[group]


def build_matrix_rows(
    dataset: WorkbookDataset,
    *,
    group: MatrixGroup,
    metric: MatrixMetric,
    weeks: set[int],
    scoring: Scoring,
) -> list[dict[str, object]]:
    """Build matrix rows using the service-layer feeder row builder."""
    from draft_api.workbook.service import _feeder_row  # local import avoids cycles at load

    feeder_group = _feeder_group_for(group, metric)

    off_values: dict[str, float | None] = {}
    def_values: dict[str, float | None] = {}
    net_values: dict[str, float | None] = {}
    for team in dataset.teams:
        row = _feeder_row(
            dataset,
            group=feeder_group,
            team=team,
            weeks=weeks,
            scoring=scoring,
        )
        off_values[team] = cast(float | None, row.get("off"))
        def_values[team] = cast(float | None, row.get("def"))
        net_values[team] = cast(float | None, row.get("net"))

    higher = _metric_higher_is_better(metric)
    off_tiers = assign_tertile(off_values, higher_is_better=higher)
    def_tiers = assign_tertile(def_values, higher_is_better=higher)
    net_tiers = assign_tertile(net_values, higher_is_better=higher)

    payload: list[dict[str, object]] = []
    for team in sorted(dataset.teams):
        payload.append(
            {
                "team": team,
                "off": _cell(off_values[team], off_tiers[team]),
                "def": _cell(def_values[team], def_tiers[team]),
                "net": _cell(net_values[team], net_tiers[team]),
            }
        )
    return payload


def build_matrix_payload(
    dataset: WorkbookDataset,
    *,
    group: MatrixGroup,
    metric: MatrixMetric,
    weeks: set[int],
    scoring: Scoring,
) -> dict[str, object]:
    teams = build_matrix_rows(
        dataset,
        group=group,
        metric=metric,
        weeks=weeks,
        scoring=scoring,
    )
    return {
        "group": group,
        "metric": metric,
        "teams": teams,
    }
