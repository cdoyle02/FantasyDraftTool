"""SoS Clay WR role index resolution and stats filtering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from draft_api.sos.clay_roles import (
    filter_stats_by_clay_role,
    filter_usage_index_by_clay_role,
    parse_wr_role,
    resolve_clay_role_index,
    ensure_wr_role_for_position,
)
from draft_api.sos.usage import PlayerUsage
from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.roles import build_role_index

FIXTURES = Path(__file__).parent.parent / "workbook" / "fixtures"


def _mini_role_index() -> dict[str, str]:
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


def _wr_stat(name: str, *, epa: str = "1", fp: str = "10") -> dict[str, str]:
    return {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "WR",
        "team": "KC",
        "opponent_team": "BUF",
        "player_display_name": name,
        "receiving_epa": epa,
        "fantasy_points_ppr": fp,
        "targets": "5",
    }


def test_parse_wr_role_defaults_to_all():
    assert parse_wr_role(None) == "all"
    assert parse_wr_role("") == "all"
    assert parse_wr_role("all") == "all"
    assert parse_wr_role("outside") == "outside"
    assert parse_wr_role("slot") == "slot"


def test_parse_wr_role_rejects_unknown():
    with pytest.raises(ValueError, match="wrRole"):
        parse_wr_role("middle")


def test_ensure_wr_role_for_position():
    ensure_wr_role_for_position("WR", "slot")
    with pytest.raises(ValueError, match="WR only"):
        ensure_wr_role_for_position("RB", "slot")


def test_filter_stats_by_clay_role_all_passes_through():
    rows = [_wr_stat("Outside Receiver"), _wr_stat("Unknown Guy")]
    assert filter_stats_by_clay_role(rows, _mini_role_index(), "all") == rows


def test_filter_stats_slot_keeps_listed_slot_only():
    rows = [
        _wr_stat("Outside Receiver"),
        _wr_stat("Slot Receiver"),
        _wr_stat("Mystery"),
    ]
    filtered = filter_stats_by_clay_role(rows, _mini_role_index(), "slot")
    assert [r["player_display_name"] for r in filtered] == ["Slot Receiver"]


def test_filter_usage_index_by_clay_role():
    usage = [
        PlayerUsage(None, "Outside Receiver", "KC", "WR", 0.6),
        PlayerUsage(None, "Slot Receiver", "KC", "WR", 0.4),
        PlayerUsage(None, "Other", "KC", "WR", 0.1),
    ]
    out = filter_usage_index_by_clay_role(usage, _mini_role_index(), "outside")
    assert [p.player_name for p in out] == ["Outside Receiver"]


def test_resolve_clay_role_index_uses_injected_override():
    injected = {"test player": "slot"}
    assert resolve_clay_role_index(2026, role_index_override=injected) == injected


def test_resolve_clay_role_index_merges_previous(monkeypatch) -> None:
    previous = {"stale guy": "outside"}

    def fake_load(_season: int, **kwargs):  # noqa: ANN001
        rows = [
            ClayWrRow(
                team="KC",
                name="Fresh",
                pos="L",
                lwr_pct=80,
                slot_pct=10,
                rwr_pct=10,
            )
        ]
        return rows

    monkeypatch.setattr(
        "draft_api.sos.clay_roles.load_clay_wr_rows",
        fake_load,
    )
    index = resolve_clay_role_index(2026, previous_clay_roles=previous, workbook_fallback=False)
    assert index["stale guy"] == "outside"
    assert index["fresh"] == "outside"
