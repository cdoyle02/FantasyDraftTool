"""Read/write packaged Workbook season snapshots for offline fallback."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from draft_api.workbook.calculate import DriveOutcome, PassPlay, TeamRateSlice
from draft_api.workbook.nflverse import PositionalWeekRate, WorkbookDataset

SNAPSHOT_NAME = "workbook_{season}.json"

_POSITIONAL_FIELDS: tuple[str, ...] = (
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
_TEAM_RATE_FIELDS: tuple[str, ...] = (
    "proe",
    "pass_plays",
    "epa_pass",
    "xplsv_pass",
    "run_plays",
    "epa_run",
    "xplsv_run",
)


class SnapshotError(RuntimeError):
    """Raised when a packaged Workbook snapshot is missing or invalid."""


def snapshot_resource_name(season: int) -> str:
    return SNAPSHOT_NAME.format(season=season)


def snapshot_path_for_write(season: int) -> Path:
    """Filesystem path inside the package data dir for the refresh command."""
    return Path(__file__).resolve().parent.parent / "data" / snapshot_resource_name(season)


def _positional_rate_to_dict(rate: PositionalWeekRate) -> dict[str, float | None]:
    return {field: getattr(rate, field) for field in _POSITIONAL_FIELDS}


def _positional_rate_from_dict(payload: dict[str, Any]) -> PositionalWeekRate:
    return PositionalWeekRate(
        **{field: _optional_float(payload.get(field)) for field in _POSITIONAL_FIELDS}
    )


def _positional_buckets_to_dict(
    buckets: dict[str, dict[tuple[str, int], PositionalWeekRate]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        group: [
            {"team": team, "week": week, "rates": _positional_rate_to_dict(rate)}
            for (team, week), rate in sorted(team_weeks.items())
        ]
        for group, team_weeks in sorted(buckets.items())
    }


def _positional_buckets_from_dict(
    payload: dict[str, Any],
) -> dict[str, dict[tuple[str, int], PositionalWeekRate]]:
    out: dict[str, dict[tuple[str, int], PositionalWeekRate]] = {}
    for group, rows in payload.items():
        group_rates: dict[tuple[str, int], PositionalWeekRate] = {}
        for row in rows or []:
            if not isinstance(row, dict):
                raise SnapshotError("positional rows must be JSON objects")
            team = str(row["team"])
            week = int(row["week"])
            rates = row.get("rates") or {}
            if not isinstance(rates, dict):
                raise SnapshotError("positional rates must be JSON objects")
            group_rates[(team, week)] = _positional_rate_from_dict(rates)
        out[str(group)] = group_rates
    return out


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _team_rate_to_dict(rate: TeamRateSlice) -> dict[str, Any]:
    return {
        "team": rate.team,
        "week": rate.week,
        "side": rate.side,
        **{field: getattr(rate, field) for field in _TEAM_RATE_FIELDS},
    }


def _team_rate_from_dict(payload: dict[str, Any]) -> TeamRateSlice:
    return TeamRateSlice(
        team=str(payload["team"]),
        week=int(payload["week"]),
        side=payload["side"],
        **{field: _optional_float(payload.get(field)) for field in _TEAM_RATE_FIELDS},
    )


def dataset_to_dict(dataset: WorkbookDataset) -> dict[str, Any]:
    return {
        "season": dataset.season,
        "fetchedAt": dataset.fetched_at,
        "teams": list(dataset.teams),
        "schedule": {
            str(week): {team: opponent for team, opponent in teams.items()}
            for week, teams in sorted(dataset.schedule.items())
        },
        "drives": [
            {"team": drive.team, "week": drive.week, "success": drive.success}
            for drive in dataset.drives
        ],
        "passPlays": [
            {
                "team": play.team,
                "week": play.week,
                "isPass": play.is_pass,
                "xpass": play.xpass,
            }
            for play in dataset.pass_plays
        ],
        "teamEnvOff": [_team_rate_to_dict(rate) for rate in dataset.team_env_off],
        "teamEnvDef": [_team_rate_to_dict(rate) for rate in dataset.team_env_def],
        "positionalOff": _positional_buckets_to_dict(dataset.positional_off),
        "positionalDef": _positional_buckets_to_dict(dataset.positional_def),
    }


def dataset_from_dict(payload: Any) -> WorkbookDataset:
    if not isinstance(payload, dict):
        raise SnapshotError("packaged snapshot must be a JSON object")

    try:
        schedule = {
            int(week): {
                str(team): (None if opponent in (None, "", "-") else str(opponent))
                for team, opponent in (teams or {}).items()
            }
            for week, teams in (payload.get("schedule") or {}).items()
        }
        return WorkbookDataset(
            season=int(payload["season"]),
            fetched_at=str(payload.get("fetchedAt") or ""),
            teams=list(payload.get("teams") or []),
            schedule=schedule,
            drives=[
                DriveOutcome(
                    team=str(row["team"]),
                    week=int(row["week"]),
                    success=bool(row["success"]),
                )
                for row in payload.get("drives") or []
            ],
            pass_plays=[
                PassPlay(
                    team=str(row["team"]),
                    week=int(row["week"]),
                    is_pass=bool(row["isPass"]),
                    xpass=_optional_float(row.get("xpass")),
                )
                for row in payload.get("passPlays") or []
            ],
            team_env_off=[
                _team_rate_from_dict(row) for row in payload.get("teamEnvOff") or []
            ],
            team_env_def=[
                _team_rate_from_dict(row) for row in payload.get("teamEnvDef") or []
            ],
            positional_off=_positional_buckets_from_dict(
                payload.get("positionalOff") or {}
            ),
            positional_def=_positional_buckets_from_dict(
                payload.get("positionalDef") or {}
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotError("packaged snapshot has invalid Workbook shape") from exc


def write_snapshot(path: Path, dataset: WorkbookDataset) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dataset_to_dict(dataset)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_packaged_snapshot(season: int) -> WorkbookDataset:
    name = snapshot_resource_name(season)
    try:
        text = resources.files("draft_api.data").joinpath(name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise SnapshotError(f"packaged snapshot {name} not found") from exc
    try:
        return dataset_from_dict(json.loads(text))
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"packaged snapshot {name} is invalid JSON") from exc
