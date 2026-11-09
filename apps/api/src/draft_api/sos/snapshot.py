"""Read/write packaged SoS season snapshots for offline / deploy fallback."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from draft_api.sos.calculate import CompletedGame, Position
from draft_api.sos.nflverse import NFL_TEAMS, SosDataset
from draft_api.workbook.roles import Role

SNAPSHOT_NAME = "sos_{season}.json"


class SnapshotError(RuntimeError):
    """Raised when a packaged snapshot is missing or invalid."""


def _clay_roles_to_dict(roles: dict[str, Role]) -> dict[str, str]:
    return {str(name): str(role) for name, role in sorted(roles.items())}


def _clay_roles_from_dict(payload: Any) -> dict[str, Role]:
    raw = payload or {}
    if not isinstance(raw, dict):
        raise SnapshotError("clayRoles must be a JSON object")
    out: dict[str, Role] = {}
    for name, role in raw.items():
        if role not in ("slot", "outside"):
            raise SnapshotError(f"invalid Clay role {role!r} for {name!r}")
        out[str(name)] = role  # type: ignore[assignment]
    return out


def snapshot_resource_name(season: int) -> str:
    return SNAPSHOT_NAME.format(season=season)


def snapshot_path_for_write(season: int) -> Path:
    """Filesystem path inside the package data dir (for refresh command)."""
    return Path(__file__).resolve().parent.parent / "data" / snapshot_resource_name(season)


def dataset_to_dict(dataset: SosDataset) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "season": dataset.season,
        "fetchedAt": dataset.fetched_at,
        "teams": list(dataset.teams),
        "schedule": {
            team: {str(week): opponent for week, opponent in weeks.items()}
            for team, weeks in dataset.schedule.items()
        },
        "games": [
            {
                "week": game.week,
                "offense": game.offense,
                "defense": game.defense,
                "points": {
                    pos: game.points.get(pos, 0.0)
                    for pos in ("QB", "RB", "WR", "TE", "DST")
                },
            }
            for game in dataset.games
        ],
    }
    if dataset.usage_stats:
        payload["usageStats"] = list(dataset.usage_stats)
    if dataset.snap_counts:
        payload["snapCounts"] = list(dataset.snap_counts)
    if dataset.clay_roles:
        payload["clayRoles"] = _clay_roles_to_dict(dataset.clay_roles)
    return payload


def dataset_from_dict(payload: dict[str, Any]) -> SosDataset:
    season = int(payload["season"])
    teams = list(payload.get("teams") or NFL_TEAMS)
    raw_schedule = payload.get("schedule") or {}
    schedule: dict[str, dict[int, str | None]] = {}
    for team, weeks in raw_schedule.items():
        schedule[team] = {
            int(week): (None if opponent in (None, "", "-") else str(opponent))
            for week, opponent in weeks.items()
        }
    games: list[CompletedGame] = []
    for row in payload.get("games") or []:
        points_raw = row.get("points") or {}
        points: dict[Position, float] = {
            "QB": float(points_raw.get("QB", 0.0) or 0.0),
            "RB": float(points_raw.get("RB", 0.0) or 0.0),
            "WR": float(points_raw.get("WR", 0.0) or 0.0),
            "TE": float(points_raw.get("TE", 0.0) or 0.0),
            "DST": float(points_raw.get("DST", 0.0) or 0.0),
        }
        games.append(
            CompletedGame(
                week=int(row["week"]),
                offense=str(row["offense"]),
                defense=str(row["defense"]),
                points=points,
            )
        )
    usage_stats: tuple[dict[str, str | None], ...] = ()
    raw_usage = payload.get("usageStats")
    if raw_usage is not None:
        if not isinstance(raw_usage, list):
            raise SnapshotError("usageStats must be a JSON array")
        usage_stats = tuple(
            {str(k): (None if v is None else str(v)) for k, v in dict(row).items()}
            for row in raw_usage
            if isinstance(row, dict)
        )

    snap_counts: tuple[dict[str, str | None], ...] = ()
    raw_snaps = payload.get("snapCounts")
    if raw_snaps is not None:
        if not isinstance(raw_snaps, list):
            raise SnapshotError("snapCounts must be a JSON array")
        snap_counts = tuple(
            {str(k): (None if v is None else str(v)) for k, v in dict(row).items()}
            for row in raw_snaps
            if isinstance(row, dict)
        )

    return SosDataset(
        season=season,
        fetched_at=str(payload.get("fetchedAt") or ""),
        games=games,
        schedule=schedule,
        teams=teams,
        usage_stats=usage_stats,
        snap_counts=snap_counts,
        clay_roles=_clay_roles_from_dict(payload.get("clayRoles")),
    )


def write_snapshot(dataset: SosDataset, path: Path | None = None) -> Path:
    target = path or snapshot_path_for_write(dataset.season)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dataset_to_dict(dataset), indent=2) + "\n", encoding="utf-8")
    return target


def read_packaged_snapshot(season: int) -> SosDataset:
    name = snapshot_resource_name(season)
    try:
        text = resources.files("draft_api.data").joinpath(name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise SnapshotError(f"packaged snapshot {name} not found") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"packaged snapshot {name} is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise SnapshotError(f"packaged snapshot {name} must be a JSON object")
    return dataset_from_dict(payload)
