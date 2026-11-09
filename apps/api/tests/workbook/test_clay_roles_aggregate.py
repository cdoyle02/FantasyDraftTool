"""Clay role → Out/Slot WR OFF/DEF aggregation from stats_player_week rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.nflverse import aggregate_out_slot_from_stats
from draft_api.workbook.roles import build_role_index

FIXTURES = Path(__file__).parent / "fixtures"
SEASON = 2026


def _load_mini_role_index() -> dict[str, str]:
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


def _wr_row(
    name: str,
    *,
    targets: str = "5",
    receptions: str = "4",
    yards: str = "60",
    tds: str = "1",
    fp: str = "16.0",
) -> dict[str, str]:
    return {
        "season": str(SEASON),
        "season_type": "REG",
        "week": "5",
        "player_id": "X",
        "position": "WR",
        "team": "KC",
        "opponent_team": "BUF",
        "player_display_name": name,
        "targets": targets,
        "receptions": receptions,
        "receiving_yards": yards,
        "receiving_tds": tds,
        "carries": "0",
        "rushing_yards": "0",
        "rushing_tds": "0",
        "passing_yards": "0",
        "passing_tds": "0",
        "fantasy_points_ppr": fp,
    }


def test_aggregate_splits_out_slot_off_and_def() -> None:
    role_index = _load_mini_role_index()
    rows = [
        _wr_row("Outside Receiver"),
        _wr_row(
            "Slot Receiver",
            targets="3",
            receptions="2",
            yards="15",
            tds="0",
            fp="5.5",
        ),
    ]
    off, def_ = aggregate_out_slot_from_stats(rows, role_index, season=SEASON)

    out_off = off["out_wr"][("KC", 5)]
    assert out_off.targets == pytest.approx(5.0)
    assert out_off.receptions == pytest.approx(4.0)
    assert out_off.rec_yards == pytest.approx(60.0)
    assert out_off.rec_tds == pytest.approx(1.0)
    assert out_off.fantasy_points == pytest.approx(16.0)  # 4 + 60*0.1 + 6

    slot_off = off["slot_wr"][("KC", 5)]
    assert slot_off.targets == pytest.approx(3.0)
    assert slot_off.rec_yards == pytest.approx(15.0)
    assert slot_off.fantasy_points == pytest.approx(3.5)

    out_def = def_["out_wr"][("BUF", 5)]
    assert out_def.targets == pytest.approx(5.0)
    assert out_def.rec_yards == pytest.approx(60.0)

    slot_def = def_["slot_wr"][("BUF", 5)]
    assert slot_def.targets == pytest.approx(3.0)
    assert slot_def.rec_yards == pytest.approx(15.0)


def test_aggregate_skips_wr_without_clay_role() -> None:
    role_index = _load_mini_role_index()
    rows = [_wr_row("Unknown WR")]
    off, def_ = aggregate_out_slot_from_stats(rows, role_index, season=SEASON)
    assert off["out_wr"] == {}
    assert off["slot_wr"] == {}
    assert def_["out_wr"] == {}
    assert def_["slot_wr"] == {}


def test_aggregate_ignores_non_wr_positions() -> None:
    role_index = _load_mini_role_index()
    rows = [
        {
            **_wr_row("Outside Receiver"),
            "position": "TE",
        }
    ]
    off, def_ = aggregate_out_slot_from_stats(rows, role_index, season=SEASON)
    assert off["out_wr"] == {}
