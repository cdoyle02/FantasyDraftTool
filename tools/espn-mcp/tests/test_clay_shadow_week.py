"""MCP clay_shadow_week + player_intel bridges (mocked draft_api)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from espn_mcp.draft_bridge import clay_shadow_week, player_intel


def test_clay_shadow_week_returns_payload() -> None:
    with (
        patch(
            "espn_mcp.draft_bridge.active_config",
            return_value=SimpleNamespace(season=2026),
        ),
        patch(
            "draft_api.workbook.service.build_clay_shadow_response",
            return_value={
                "season": 2026,
                "week": 9,
                "shadows": [{"receiver": "Ja'Marr Chase", "defender": "CJ Henderson"}],
                "warnings": [],
            },
        ),
    ):
        raw = clay_shadow_week(week=9)
    assert "Ja'Marr Chase" in raw
    assert "CJ Henderson" in raw


def test_player_intel_returns_payload() -> None:
    with (
        patch(
            "espn_mcp.draft_bridge.active_config",
            return_value=SimpleNamespace(season=2026),
        ),
        patch(
            "draft_api.workbook.service.build_player_intel_response",
            return_value={
                "player": {"name": "Ja'Marr Chase", "team": "CIN"},
                "clayRole": "outside",
                "clayShadow": {"defender": "CJ Henderson"},
                "injury": None,
                "sosOpportunity": None,
            },
        ),
    ):
        raw = player_intel("Ja'Marr Chase", week=9, team="CIN")
    assert "outside" in raw
    assert "CJ Henderson" in raw
