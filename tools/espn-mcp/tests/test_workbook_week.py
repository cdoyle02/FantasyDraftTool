"""Contract tests for MCP workbook_week bridge (mocked draft_api)."""

from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from espn_mcp.draft_bridge import workbook_week

MOCK_BOARD = {
    "season": 2026,
    "week": 10,
    "window": "l4",
    "scoring": "ppr",
    "slate": "main",
    "ratedThroughWeek": 9,
    "fetchedAt": "2026-11-08T12:00:00Z",
    "source": "nflverse",
    "stale": False,
    "attribution": "test attribution",
    "games": [
        {
            "away": "NYJ",
            "home": "NE",
            "kickoff": "2026-11-09T18:00:00Z",
            "mainSlate": True,
            "rows": [
                {
                    "team": "NE",
                    "homeAway": "home",
                    "opponent": "NYJ",
                    "gameEnvironment": {
                        "netDsr": 0.55,
                        "vegasImpliedPoints": 24.5,
                        "combNetDsr": 0.52,
                        "netDsrDiff": 0.03,
                    },
                    "qb": {"fpGTot": 18.2},
                    "allWr": {"fpG": 12.0},
                    "outWr": {"fpG": None},
                    "slotWr": {"fpG": None},
                    "te": {"fpG": 8.5},
                    "rb": {"fpGTot": 15.0},
                }
            ],
        }
    ],
    "highlights": [
        {
            "playerId": 1,
            "displayName": "Allen Lazard",
            "nflTeam": "NE",
            "matchupTeam": "NE",
            "opponent": "NYJ",
            "role": "roster",
            "rosterSlot": "WR",
        }
    ],
    "joinStats": {"matched": 1, "unmatched_team": 0, "unmatched_name_only": 0},
}


class EspnRosterError(Exception):
    pass


@pytest.fixture
def mock_league_bridge():
    with patch("espn_mcp.draft_bridge._league", return_value={"id": "1216398267", "name": "Girls Who Ball"}):
        with patch(
            "espn_mcp.draft_bridge.active_config",
            return_value=MagicMock(season=2026, espn_s2="s2", swid="{swid}"),
        ):
            yield


@pytest.fixture
def draft_api_modules(monkeypatch):
    build = MagicMock(return_value=MOCK_BOARD.copy())
    main = ModuleType("draft_api.main")
    main.get_kyle_dst_rankings_cached = MagicMock(return_value={"week": 10})

    service = ModuleType("draft_api.workbook.service")
    service.build_matchups_response = build

    espn_roster = ModuleType("draft_api.espn_roster")
    espn_roster.EspnRosterError = EspnRosterError
    espn_roster.load_espn_overlay_players = MagicMock(return_value=([], [], None))

    workbook = ModuleType("draft_api.workbook")
    workbook.service = service

    draft_api = ModuleType("draft_api")
    draft_api.main = main
    draft_api.workbook = workbook
    draft_api.espn_roster = espn_roster

    for name, mod in [
        ("draft_api", draft_api),
        ("draft_api.main", main),
        ("draft_api.workbook", workbook),
        ("draft_api.workbook.service", service),
        ("draft_api.espn_roster", espn_roster),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)

    return {"build": build, "load_overlay": espn_roster.load_espn_overlay_players, "rankings": main}


def test_workbook_week_returns_trimmed_board(mock_league_bridge, draft_api_modules) -> None:
    raw = workbook_week(league="Girls Who Ball", week=10, include_highlights=True)
    payload = json.loads(raw)
    assert payload["week"] == 10
    assert payload["league"]["id"] == "1216398267"
    assert len(payload["games"]) == 1
    row = payload["games"][0]["rows"][0]
    assert row["team"] == "NE"
    assert "netDsr" in row["gameEnvironment"]
    assert row["qb"]["fpGTot"] == 18.2
    assert payload["highlights"][0]["displayName"] == "Allen Lazard"
    assert payload["attribution"] == "test attribution"
    assert payload["stale"] is False
    draft_api_modules["build"].assert_called_once()
    call_kw = draft_api_modules["build"].call_args.kwargs
    assert call_kw["league_id"] == "1216398267"
    assert call_kw["week"] == 10


def test_workbook_week_default_week_from_rankings(mock_league_bridge, draft_api_modules) -> None:
    draft_api_modules["rankings"].get_kyle_dst_rankings_cached.return_value = {"week": 11}
    draft_api_modules["build"].return_value = {**MOCK_BOARD, "week": 11}
    workbook_week(league="1216398267", week=None)
    assert draft_api_modules["build"].call_args.kwargs["week"] == 11


def test_workbook_week_owner_warning_when_unresolved(mock_league_bridge, draft_api_modules) -> None:
    draft_api_modules["load_overlay"].return_value = ([], [], None)
    raw = workbook_week(league="Girls Who Ball", owner="Nobody Here")
    payload = json.loads(raw)
    assert any("Nobody Here" in w for w in payload.get("warnings", []))


def test_workbook_week_skips_highlights_when_disabled(mock_league_bridge, draft_api_modules) -> None:
    workbook_week(league="Girls Who Ball", include_highlights=False)
    assert draft_api_modules["build"].call_args.kwargs["league_id"] is None
