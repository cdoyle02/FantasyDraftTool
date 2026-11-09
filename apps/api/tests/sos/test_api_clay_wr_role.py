"""HTTP wrRole validation and WR Out/Slot split behavior."""

from __future__ import annotations

import json
from pathlib import Path

from draft_api.main import app
from draft_api.sos.calculate import CompletedGame
from draft_api.sos.clay_roles import set_sos_clay_role_index_override
from draft_api.sos.nflverse import SosDataset
from draft_api.sos.service import (
    clear_sos_cache,
    set_sos_dataset_override,
    set_sos_stats_rows_override,
)
from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.roles import build_role_index
from fastapi.testclient import TestClient

client = TestClient(app)
FIXTURES = Path(__file__).parent.parent / "workbook" / "fixtures"


def _roles() -> dict[str, str]:
    raw = json.loads((FIXTURES / "clay_roles_mini.json").read_text())
    rows = [
        ClayWrRow(
            team=item["team"],
            name=item["name"],
            pos=item["pos"],  # type: ignore[arg-type]
            lwr_pct=item["lwr_pct"],
            slot_pct=item["slot_pct"],
            rwr_pct=item["rwr_pct"],
        )
        for item in raw
    ]
    return build_role_index(rows)


def setup_function() -> None:
    clear_sos_cache()
    pts = {"QB": 0.0, "RB": 0.0, "TE": 0.0, "DST": 0.0}
    set_sos_dataset_override(
        SosDataset(
            season=2026,
            fetched_at="2026-11-08T12:00:00Z",
            games=[
                CompletedGame(week=1, offense="OFF1", defense="DEF_A", points={**pts, "WR": 17.0}),
                CompletedGame(week=2, offense="OFF1", defense="DEF_B", points={**pts, "WR": 20.0}),
            ],
            schedule={
                "OFF1": {**{w: None for w in range(1, 19)}, 1: "DEF_A", 2: "DEF_B"},
                "DEF_A": {**{w: None for w in range(1, 19)}, 1: "OFF1"},
                "DEF_B": {**{w: None for w in range(1, 19)}, 2: "OFF1"},
            },
            teams=["OFF1", "DEF_A", "DEF_B"],
        )
    )
    set_sos_clay_role_index_override(_roles())
    set_sos_stats_rows_override(
        [
            {
                "season": "2026",
                "week": "1",
                "season_type": "REG",
                "position": "WR",
                "team": "OFF1",
                "opponent_team": "DEF_A",
                "player_display_name": "Slot Receiver",
                "receiving_epa": "5",
                "fantasy_points_ppr": "6",
                "targets": "4",
            },
            {
                "season": "2026",
                "week": "1",
                "season_type": "REG",
                "position": "WR",
                "team": "OFF1",
                "opponent_team": "DEF_A",
                "player_display_name": "Outside Receiver",
                "receiving_epa": "25",
                "fantasy_points_ppr": "30",
                "targets": "8",
            },
            {
                "season": "2026",
                "week": "2",
                "season_type": "REG",
                "position": "WR",
                "team": "OFF1",
                "opponent_team": "DEF_B",
                "player_display_name": "Slot Receiver",
                "receiving_epa": "18",
                "fantasy_points_ppr": "22",
                "targets": "7",
            },
            {
                "season": "2026",
                "week": "2",
                "season_type": "REG",
                "position": "WR",
                "team": "OFF1",
                "opponent_team": "DEF_B",
                "player_display_name": "Outside Receiver",
                "receiving_epa": "2",
                "fantasy_points_ppr": "4",
                "targets": "2",
            },
        ]
    )


def teardown_function() -> None:
    set_sos_dataset_override(None)
    set_sos_stats_rows_override(None)
    set_sos_clay_role_index_override(None)
    clear_sos_cache()


def test_wr_role_rejected_for_rb():
    response = client.get(
        "/api/v1/nfl/strength-of-schedule/tier2",
        params={"position": "RB", "wrRole": "slot", "season": 2026},
    )
    assert response.status_code == 400


def test_tier2_wr_slot_softens_def_a_in_grid():
    all_resp = client.get(
        "/api/v1/nfl/strength-of-schedule/tier2",
        params={"position": "WR", "season": 2026, "startWeek": 1, "endWeek": 2},
    )
    slot_resp = client.get(
        "/api/v1/nfl/strength-of-schedule/tier2",
        params={"position": "WR", "wrRole": "slot", "season": 2026, "startWeek": 1, "endWeek": 2},
    )
    assert all_resp.status_code == 200
    assert slot_resp.status_code == 200
    assert slot_resp.json().get("wrRole") == "slot"
    all_off = next(t for t in all_resp.json()["teams"] if t["team"] == "OFF1")
    slot_off = next(t for t in slot_resp.json()["teams"] if t["team"] == "OFF1")
    w1_all = next(c for c in all_off["weeks"] if c["week"] == 1)
    w1_slot = next(c for c in slot_off["weeks"] if c["week"] == 1)
    w2_all = next(c for c in all_off["weeks"] if c["week"] == 2)
    w2_slot = next(c for c in slot_off["weeks"] if c["week"] == 2)
    assert w1_all["rank"] == 1
    assert w2_slot["rank"] == 1
    assert w1_slot["rank"] != w1_all["rank"]
    assert w2_all["rank"] != w2_slot["rank"]
