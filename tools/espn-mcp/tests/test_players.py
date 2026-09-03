from __future__ import annotations

import pytest

from espn_mcp.client import EspnError
from espn_mcp.players import (
    is_available,
    normalize_player_entry,
    normalize_position_alias,
    pagination_fields,
    select_stat,
    validate_free_agent_query,
)
from tests.fixtures.kona_entries import DST_ENTRY, MINIMAL_ENTRY, ONTEAM_ENTRY, WAIVER_ENTRY


def test_normalize_position_aliases() -> None:
    assert normalize_position_alias("d/st") == "DST"
    assert normalize_position_alias("DEF") == "DST"
    assert normalize_position_alias("QB") == "QB"


def test_is_available_uses_status_only() -> None:
    assert is_available("WAIVERS") is True
    assert is_available("FREEAGENT") is True
    assert is_available("ONTEAM") is False
    assert is_available(None) is False


def test_select_stat_requires_season() -> None:
    stats = WAIVER_ENTRY["player"]["stats"]
    selected = select_stat(stats, season=2020, source=0, split=0, scoring_period=0)
    assert selected is not None
    assert selected["appliedTotal"] == 134.8
    prior = select_stat(stats, season=2019, source=0, split=0, scoring_period=0)
    assert prior is not None
    assert prior["appliedTotal"] == 999.0
    assert select_stat(stats, season=2021, source=0, split=0, scoring_period=0) is None


def test_normalize_waiver_entry() -> None:
    row = normalize_player_entry(WAIVER_ENTRY, season=2020, scoring_period_id=16)
    assert row["status"] == "WAIVERS"
    assert row["on_team_id"] == 0
    assert row["is_available"] is True
    assert row["position"] == "WR"
    assert row["season_actual_points"] == 134.8
    assert row["season_projected_points"] == 169.5
    assert row["weekly_actual_points"] == 12.4
    assert row["waiver_process_timestamp_ms"] == 1615993200000
    assert row["waiver_process_at"] is not None


def test_normalize_onteam_not_available() -> None:
    row = normalize_player_entry(ONTEAM_ENTRY, season=2020, scoring_period_id=None)
    assert row["status"] == "ONTEAM"
    assert row["is_available"] is False


def test_normalize_dst_and_unknowns() -> None:
    row = normalize_player_entry(DST_ENTRY, season=2020, scoring_period_id=None)
    assert row["position"] == "DST"
    assert row["name"] == "Seahawks D/ST"

    minimal = normalize_player_entry(MINIMAL_ENTRY, season=2020, scoring_period_id=None)
    assert minimal["position"] == "UNKNOWN"
    assert minimal["pro_team"] == "UNK"
    assert minimal["percent_owned"] is None
    assert minimal["injury_status"] is None


def test_zero_stat_preserved() -> None:
    entry = {
        "id": 1,
        "status": "WAIVERS",
        "player": {
            "id": 1,
            "fullName": "Zero Week",
            "defaultPositionId": 2,
            "proTeamId": 1,
            "stats": [
                {
                    "seasonId": 2020,
                    "statSourceId": 0,
                    "statSplitTypeId": 1,
                    "scoringPeriodId": 16,
                    "appliedTotal": 0.0,
                }
            ],
        },
    }
    row = normalize_player_entry(entry, season=2020, scoring_period_id=16)
    assert row["weekly_actual_points"] == 0.0


def test_validate_free_agent_query_errors() -> None:
    with pytest.raises(EspnError, match="league id"):
        validate_free_agent_query(
            league_id=None,
            season=2020,
            statuses=None,
            position=None,
            limit=50,
            offset=0,
            sort_by="percent_owned",
            sort_asc=False,
            scoring_period_id=None,
            search=None,
        )
    with pytest.raises(EspnError, match="statuses"):
        validate_free_agent_query(
            league_id="1",
            season=2020,
            statuses=["ONTEAM"],
            position=None,
            limit=50,
            offset=0,
            sort_by="percent_owned",
            sort_asc=False,
            scoring_period_id=None,
            search=None,
        )
    with pytest.raises(EspnError, match="limit"):
        validate_free_agent_query(
            league_id="1",
            season=2020,
            statuses=None,
            position=None,
            limit=0,
            offset=0,
            sort_by="percent_owned",
            sort_asc=False,
            scoring_period_id=None,
            search=None,
        )


def test_pagination_fields() -> None:
    page = pagination_fields(offset=10, limit=5, returned=5)
    assert page["has_more"] is True
    assert page["next_offset"] == 15
    short = pagination_fields(offset=10, limit=5, returned=2)
    assert short["has_more"] is False
    assert short["next_offset"] is None
