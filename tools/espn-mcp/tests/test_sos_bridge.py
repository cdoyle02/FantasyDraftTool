"""Contract tests for MCP sos_grid / sos_opportunity bridges (mocked draft_api)."""

from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from espn_mcp.client import EspnError
from espn_mcp.draft_bridge import sos_grid, sos_opportunity

MOCK_GRID = {
    "season": 2026,
    "position": "RB",
    "window": "l8",
    "startWeek": 1,
    "endWeek": 17,
    "ratedThroughWeek": 9,
    "ratingWeeks": [2, 3, 4, 5, 6, 7, 8, 9],
    "shrinkK": 4,
    "fetchedAt": "2026-11-08T12:00:00Z",
    "source": "nflverse",
    "stale": False,
    "leagueId": "169429",
    "leagueName": "Florida Football Federation",
    "teams": [
        {
            "team": "DEN",
            "rank": 1,
            "opponentAverage": 23.1,
            "primaryPlayer": {"name": "J.K. Dobbins", "team": "DEN", "position": "RB"},
            "leagueAvailability": "taken",
            "weeks": [
                {
                    "week": 9,
                    "opponent": "HOU",
                    "rank": 4,
                    "softness": "soft",
                    "bye": False,
                    "inWindow": True,
                    "shrunkAfpa": 24.0,
                },
                {
                    "week": 10,
                    "opponent": None,
                    "rank": None,
                    "softness": None,
                    "bye": True,
                    "inWindow": True,
                    "shrunkAfpa": None,
                },
                {
                    "week": 11,
                    "opponent": "KC",
                    "rank": 12,
                    "softness": "neutral",
                    "bye": False,
                    "inWindow": True,
                    "shrunkAfpa": 21.0,
                },
            ],
        }
    ],
}

MOCK_OPP = {
    "season": 2026,
    "position": "RB",
    "window": "l8",
    "week": 10,
    "ratedThroughWeek": 9,
    "ratingWeeks": [2, 3, 4, 5, 6, 7, 8, 9],
    "fetchedAt": "2026-11-08T12:00:00Z",
    "source": "nflverse",
    "stale": False,
    "leagueId": "169429",
    "leagueName": "Florida Football Federation",
    "joinStats": {"matched": 1, "unmatched": 0, "skippedPosition": 0},
    "players": [
        {
            "name": "James Cook III",
            "team": "BUF",
            "position": "RB",
            "week": 10,
            "opponent": "NYJ",
            "opponentRank": 3,
            "softness": "soft",
            "usageShare": 0.9,
            "opportunity": 0.9,
            "bye": False,
            "joinStatus": "matched",
            "lineupSlot": "RB",
            "injuryStatus": "ACTIVE",
            "espnTeamId": 12,
        },
        {
            "name": "Bench Back",
            "team": "FA",
            "position": "RB",
            "week": 10,
            "opponent": "CHI",
            "opponentRank": 20,
            "softness": "tough",
            "usageShare": 0.1,
            "opportunity": 0.0,
            "bye": False,
            "joinStatus": "unmatched",
        },
    ],
}


@pytest.fixture
def mock_league_bridge():
    with patch(
        "espn_mcp.draft_bridge._league",
        return_value={"id": "169429", "name": "Florida Football Federation"},
    ):
        with patch(
            "espn_mcp.draft_bridge.active_config",
            return_value=MagicMock(season=2026, espn_s2="s2", swid="{swid}"),
        ):
            yield


@pytest.fixture
def draft_api_sos_modules(monkeypatch):
    clay = ModuleType("draft_api.sos.clay_roles")
    clay.parse_wr_role = MagicMock(side_effect=lambda value: (value or "all").lower())

    service = ModuleType("draft_api.sos.service")
    service.build_tier1_strength_of_schedule_response = MagicMock(return_value=MOCK_GRID.copy())
    service.build_tier2_strength_of_schedule_response = MagicMock(
        return_value={**MOCK_GRID, "position": "RB"}
    )
    service.build_tier1_opportunity_response = MagicMock(return_value=MOCK_OPP.copy())
    service.build_tier2_opportunity_response = MagicMock(return_value=MOCK_OPP.copy())

    sos = ModuleType("draft_api.sos")
    sos.clay_roles = clay
    sos.service = service

    draft_api = ModuleType("draft_api")
    draft_api.sos = sos
    draft_api.main = ModuleType("draft_api.main")
    draft_api.main.get_kyle_dst_rankings_cached = MagicMock(return_value={"week": 10})

    for name, mod in [
        ("draft_api", draft_api),
        ("draft_api.main", draft_api.main),
        ("draft_api.sos", sos),
        ("draft_api.sos.clay_roles", clay),
        ("draft_api.sos.service", service),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)

    return {"clay": clay, "service": service, "main": draft_api.main}


def test_sos_grid_trims_past_weeks_and_passes_league(mock_league_bridge, draft_api_sos_modules) -> None:
    raw = sos_grid("Florida Football Federation", "RB", tier=1, window="l8")
    payload = json.loads(raw)
    assert payload["tier"] == 1
    assert payload["fromWeek"] == 10
    assert payload["league"]["id"] == "169429"
    team = payload["teams"][0]
    assert team["team"] == "DEN"
    assert team["leagueAvailability"] == "taken"
    assert [w["week"] for w in team["weeks"]] == [10, 11]
    call_kw = draft_api_sos_modules["service"].build_tier1_strength_of_schedule_response.call_args.kwargs
    assert call_kw["league_id"] == "169429"
    assert call_kw["position"] == "RB"
    assert call_kw["window"] == "l8"


def test_sos_grid_tier2_rejects_dst(mock_league_bridge, draft_api_sos_modules) -> None:
    with pytest.raises(EspnError, match="Tier 2"):
        sos_grid("169429", "DST", tier=2)


def test_sos_opportunity_top_n_and_default_week(mock_league_bridge, draft_api_sos_modules) -> None:
    raw = sos_opportunity("169429", "rb", tier=1, top_n=1)
    payload = json.loads(raw)
    assert payload["returned"] == 1
    assert payload["playerCount"] == 2
    assert payload["players"][0]["name"] == "James Cook III"
    call_kw = draft_api_sos_modules["service"].build_tier1_opportunity_response.call_args.kwargs
    assert call_kw["week"] == 10
    assert call_kw["league_id"] == "169429"


def test_sos_opportunity_tier2_calls_tier2_builder(mock_league_bridge, draft_api_sos_modules) -> None:
    sos_opportunity("169429", "WR", tier=2, week=11, wr_role="slot")
    draft_api_sos_modules["clay"].parse_wr_role.assert_called_with("slot")
    call_kw = draft_api_sos_modules["service"].build_tier2_opportunity_response.call_args.kwargs
    assert call_kw["week"] == 11
    assert call_kw["wr_role"] == "slot"
