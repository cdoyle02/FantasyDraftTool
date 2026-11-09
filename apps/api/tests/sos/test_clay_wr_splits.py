"""Tier 1/2 WR Out/Slot splits change defensive ranks."""

from __future__ import annotations

import json
from pathlib import Path

from draft_api.sos.calculate import CompletedGame
from draft_api.sos.clay_roles import filter_stats_by_clay_role
from draft_api.sos.tier1 import build_defense_softness_index, build_tier1_grid
from draft_api.sos.tier2 import build_tier2_grid
from draft_api.sos.tier2_epa import build_defense_epa_softness_index
from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.roles import build_role_index

FIXTURES = Path(__file__).parent.parent / "workbook" / "fixtures"

TEAMS = ["DEF_A", "DEF_B"]


def _role_index() -> dict[str, str]:
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


def _games() -> list[CompletedGame]:
    base = {"QB": 0.0, "RB": 0.0, "TE": 0.0, "DST": 0.0}
    return [
        CompletedGame(
            week=1,
            offense="OFF1",
            defense="DEF_A",
            points={**base, "WR": 15.0},
        ),
        CompletedGame(
            week=2,
            offense="OFF1",
            defense="DEF_B",
            points={**base, "WR": 22.0},
        ),
    ]


def _schedule() -> dict[str, dict[int, str | None]]:
    blank = {w: None for w in range(1, 19)}
    return {
        "OFF1": {**blank, 1: "DEF_A", 2: "DEF_B"},
        "DEF_A": {**blank, 1: "OFF1"},
        "DEF_B": {**blank, 2: "OFF1"},
    }


def _stats_rows() -> list[dict[str, str]]:
    """All-WR view: DEF_A softer; slot-only: DEF_B softer."""
    rows = [
        {
            "season": "2026",
            "week": "1",
            "season_type": "REG",
            "position": "WR",
            "team": "OFF1",
            "opponent_team": "DEF_A",
            "player_display_name": "Slot Receiver",
            "receiving_epa": "5",
            "fantasy_points_ppr": "28",
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
            "player_display_name": "Outside Receiver",
            "receiving_epa": "2",
            "fantasy_points_ppr": "4",
            "targets": "2",
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
            "fantasy_points_ppr": "5",
            "targets": "7",
        },
    ]
    return rows


def test_tier2_slot_ranks_def_a_softer_than_outside():
    roles = _role_index()
    stats_all = _stats_rows()
    stats_slot = filter_stats_by_clay_role(stats_all, roles, "slot")
    _, _, all_soft = build_defense_epa_softness_index(
        position="WR",
        window="season",
        games=_games(),
        stats_rows=stats_all,
        teams=TEAMS,
    )
    _, _, slot_soft = build_defense_epa_softness_index(
        position="WR",
        window="season",
        games=_games(),
        stats_rows=stats_slot,
        teams=TEAMS,
    )
    assert all_soft["DEF_A"].rank != slot_soft["DEF_A"].rank
    assert all_soft["DEF_A"].rank == 1
    assert slot_soft["DEF_B"].rank == 1
    assert all_soft["DEF_A"].rank != slot_soft["DEF_A"].rank


def test_tier1_slot_ppr_rank_differs_from_all_wr():
    roles = _role_index()
    stats_slot = filter_stats_by_clay_role(_stats_rows(), roles, "slot")
    _, _, all_soft = build_defense_softness_index(
        position="WR",
        window="season",
        games=_games(),
        teams=TEAMS,
    )
    _, _, slot_soft = build_defense_softness_index(
        position="WR",
        window="season",
        games=_games(),
        teams=TEAMS,
        stats_rows=stats_slot,
        wr_role="slot",
    )
    assert all_soft["DEF_B"].rank == 1
    assert slot_soft["DEF_A"].rank == 1


def test_tier2_grid_wr_role_slot_changes_opponent_rank():
    roles = _role_index()
    stats = filter_stats_by_clay_role(_stats_rows(), roles, "slot")
    grid = build_tier2_grid(
        season=2026,
        position="WR",
        window="season",
        start_week=1,
        end_week=2,
        games=_games(),
        stats_rows=stats,
        season_schedule=_schedule(),
        teams=["OFF1", *TEAMS],
    )
    off1 = next(row for row in grid.teams if row.team == "OFF1")
    w1 = next(c for c in off1.weeks if c.week == 1)
    w2 = next(c for c in off1.weeks if c.week == 2)
    assert w2.rank == 1
