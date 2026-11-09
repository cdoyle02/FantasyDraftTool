from __future__ import annotations

import json

import pytest

from draft_api.sos.calculate import CompletedGame
from draft_api.sos.nflverse import SosDataset
from draft_api.sos.snapshot import SnapshotError, dataset_from_dict, write_snapshot


def _mini_dataset(
    *,
    usage_stats: tuple[dict[str, str | None], ...] = (),
    snap_counts: tuple[dict[str, str | None], ...] = (),
) -> SosDataset:
    return SosDataset(
        season=2026,
        fetched_at="2026-11-08T12:00:00Z",
        games=[
            CompletedGame(
                week=1,
                offense="KC",
                defense="BUF",
                points={"QB": 0.0, "RB": 10.0, "WR": 0.0, "TE": 0.0, "DST": 0.0},
            )
        ],
        schedule={"KC": {1: "BUF"}, "BUF": {1: "KC"}},
        teams=["BUF", "KC"],
        usage_stats=usage_stats,
        snap_counts=snap_counts,
    )


USAGE_ROW = {
    "season": "2026",
    "week": "1",
    "season_type": "REG",
    "position": "RB",
    "team": "KC",
    "player_id": "RB1",
    "player_display_name": "Test Back",
    "carries": "12",
}


SNAP_ROW = {
    "season": "2026",
    "week": "1",
    "game_type": "REG",
    "team": "KC",
    "player": "Test Back",
    "offense_pct": "0.65",
}


def test_write_snapshot_round_trips_snap_counts(tmp_path) -> None:
    dataset = _mini_dataset(snap_counts=(SNAP_ROW,))
    target = tmp_path / "sos_2026.json"
    write_snapshot(dataset, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["snapCounts"][0]["player"] == "Test Back"
    assert dataset_from_dict(payload) == dataset


def test_write_snapshot_round_trips_usage_stats(tmp_path) -> None:
    dataset = _mini_dataset(usage_stats=(USAGE_ROW,))
    target = tmp_path / "sos_2026.json"
    write_snapshot(dataset, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["usageStats"][0]["player_display_name"] == "Test Back"
    assert dataset_from_dict(payload) == dataset


def test_write_snapshot_round_trips_clay_roles(tmp_path) -> None:
    roles = {"khalil shakir": "slot", "other guy": "outside"}
    dataset = _mini_dataset()
    dataset = SosDataset(
        season=dataset.season,
        fetched_at=dataset.fetched_at,
        games=dataset.games,
        schedule=dataset.schedule,
        teams=dataset.teams,
        clay_roles=roles,
    )
    target = tmp_path / "sos_2026.json"
    write_snapshot(dataset, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["clayRoles"]["khalil shakir"] == "slot"
    assert dataset_from_dict(payload).clay_roles == dataset.clay_roles


def test_dataset_from_dict_rejects_non_array_usage_stats() -> None:
    base = _mini_dataset()
    payload = {
        "season": base.season,
        "fetchedAt": base.fetched_at,
        "teams": base.teams,
        "schedule": {"KC": {"1": "BUF"}, "BUF": {"1": "KC"}},
        "games": [
            {
                "week": 1,
                "offense": "KC",
                "defense": "BUF",
                "points": {"QB": 0, "RB": 10, "WR": 0, "TE": 0, "DST": 0},
            }
        ],
        "usageStats": {"bad": "object"},
    }
    with pytest.raises(SnapshotError, match="usageStats must be a JSON array"):
        dataset_from_dict(payload)
