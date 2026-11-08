from __future__ import annotations

import json

import pytest

from draft_api.workbook.calculate import DriveOutcome, PassPlay, TeamRateSlice
from draft_api.workbook.nflverse import PositionalWeekRate, WorkbookDataset
from draft_api.workbook.snapshot import (
    SnapshotError,
    dataset_from_dict,
    read_packaged_snapshot,
    write_snapshot,
)


def _synthetic_dataset() -> WorkbookDataset:
    return WorkbookDataset(
        season=2026,
        fetched_at="2026-11-08T12:00:00Z",
        teams=["BUF", "KC"],
        schedule={5: {"BUF": "KC", "KC": "BUF"}, 6: {"BUF": None, "KC": "DEN"}},
        drives=[
            DriveOutcome(team="KC", week=5, success=True),
            DriveOutcome(team="KC", week=5, success=False),
        ],
        pass_plays=[
            PassPlay(team="KC", week=5, is_pass=True, xpass=0.61),
            PassPlay(team="KC", week=5, is_pass=False, xpass=None),
        ],
        team_env_off=[
            TeamRateSlice(
                team="KC",
                week=5,
                side="off",
                proe=-1.25,
                pass_plays=2.0,
                epa_pass=0.2,
                xplsv_pass=0.5,
                run_plays=2.0,
                epa_run=0.075,
                xplsv_run=0.5,
            )
        ],
        team_env_def=[
            TeamRateSlice(team="BUF", week=5, side="def", proe=-1.25, pass_plays=2.0)
        ],
        positional_off={
            "qb": {("KC", 5): PositionalWeekRate(pass_yards=250.0, pass_tds=2.0)},
            "all_wr": {
                ("KC", 5): PositionalWeekRate(
                    targets=8.0,
                    receptions=6.0,
                    rec_yards=75.0,
                    rec_tds=1.0,
                    fantasy_points=21.5,
                )
            },
        },
        positional_def={
            "all_wr": {("BUF", 5): PositionalWeekRate(targets=8.0, fantasy_points=21.5)}
        },
    )


def test_write_snapshot_round_trips_workbook_dataset(tmp_path) -> None:
    target = tmp_path / "workbook_2026.json"
    dataset = _synthetic_dataset()

    write_snapshot(target, dataset)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert dataset_from_dict(payload) == dataset


def test_read_packaged_snapshot_loads_slim_2026_dataset() -> None:
    dataset = read_packaged_snapshot(2026)

    assert dataset.season == 2026
    assert dataset.teams
    assert dataset.schedule
    assert dataset.games


def test_dataset_from_dict_rejects_non_object_payload() -> None:
    with pytest.raises(SnapshotError, match="must be a JSON object"):
        dataset_from_dict([])
