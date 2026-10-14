from __future__ import annotations

import pytest

from espn_mcp.client import EspnError
from espn_mcp.transactions import (
    normalize_transactions_payload,
    parse_status_filters,
    parse_type_filters,
)


def _payload() -> dict:
    return {
        "scoringPeriodId": 6,
        "status": {
            "transactionScoringPeriod": 6,
            "waiverLastExecutionDate": 1791877086009,
            "isWaiverOrderEdited": False,
            "waiverProcessStatus": {"2026-10-07T07:05:06.736+00:00": 7},
        },
        "members": [
            {
                "id": "{katie}",
                "displayName": "Katie40890",
                "firstName": "Katie",
                "lastName": "Doyle",
            },
            {
                "id": "{rival}",
                "displayName": "Rival",
                "firstName": "Riley",
                "lastName": "Opponent",
            },
        ],
        "teams": [
            {
                "id": 11,
                "name": "BIG TDs",
                "abbrev": "BT",
                "primaryOwner": "{katie}",
                "owners": ["{katie}"],
                "waiverRank": 3,
                "transactionCounter": {
                    "acquisitions": 8,
                    "drops": 7,
                    "trades": 1,
                    "moveToActive": 12,
                    "moveToIR": 1,
                    "acquisitionBudgetSpent": 0,
                    "matchupAcquisitionTotals": {"6": 2},
                },
            },
            {
                "id": 7,
                "name": "Other Team",
                "abbrev": "OT",
                "primaryOwner": "{rival}",
                "owners": ["{rival}"],
                "waiverRank": 10,
                "transactionCounter": {"acquisitions": 2, "drops": 2, "trades": 0},
            },
        ],
        "transactions": [
            {
                "id": "pending-1",
                "type": "WAIVER",
                "status": "PENDING",
                "executionType": "EXECUTE",
                "isPending": True,
                "scoringPeriodId": 6,
                "proposedDate": 2000,
                "bidAmount": 0,
                "subOrder": 5,
                "teamId": 11,
                "memberId": "{katie}",
                "items": [
                    {
                        "type": "ADD",
                        "playerId": 101,
                        "fromTeamId": 0,
                        "toTeamId": 11,
                        "fromLineupSlotId": -1,
                        "toLineupSlotId": -1,
                        "isKeeper": False,
                    },
                    {
                        "type": "DROP",
                        "playerId": 102,
                        "fromTeamId": 11,
                        "toTeamId": 0,
                        "fromLineupSlotId": 20,
                        "toLineupSlotId": -1,
                        "isKeeper": False,
                    },
                ],
            },
            {
                "id": "done-1",
                "type": "ROSTER",
                "status": "EXECUTED",
                "executionType": "EXECUTE",
                "isPending": False,
                "scoringPeriodId": 5,
                "proposedDate": 1000,
                "teamId": 7,
                "memberId": "{rival}",
                "items": [
                    {
                        "type": "DROP",
                        "playerId": 103,
                        "fromTeamId": 7,
                        "toTeamId": 0,
                        "fromLineupSlotId": 4,
                        "toLineupSlotId": -1,
                        "isKeeper": False,
                    }
                ],
            },
        ],
    }


def test_normalize_transactions_includes_waiver_and_team_summaries() -> None:
    players = {
        101: {"player_name": "Waiver Pickup", "position": "WR", "pro_team": "PHI"},
        102: {"player_name": "Dropped Back", "position": "RB", "pro_team": "DAL"},
    }
    result = normalize_transactions_payload(
        _payload(),
        league_id="1216398267",
        league_name="Girls Who Ball",
        players=players,
        types={"WAIVER"},
        limit=10,
    )
    assert result["matched"] == 1
    assert result["returned"] == 1
    tx = result["transactions"][0]
    assert tx["type"] == "WAIVER"
    assert tx["status"] == "PENDING"
    assert tx["team_name"] == "BIG TDs"
    assert tx["owner_display_name"] == "Katie40890"
    assert tx["items"][0]["player_name"] == "Waiver Pickup"
    assert tx["items"][0]["from_team"] == "Free Agency / Waivers"
    assert tx["items"][1]["from_lineup_slot"] == "BENCH"
    assert result["waiver_status"]["recent_waiver_runs"]
    by_name = {row["team_name"]: row for row in result["team_summaries"]}
    assert by_name["BIG TDs"]["waiver_rank"] == 3
    assert by_name["BIG TDs"]["acquisitions"] == 8


def test_normalize_transactions_owner_and_pending_filters() -> None:
    result = normalize_transactions_payload(
        _payload(),
        league_id="1216398267",
        league_name="Girls Who Ball",
        owner_query="Katie",
        pending_only=True,
        limit=10,
    )
    assert result["matched"] == 1
    assert result["transactions"][0]["id"] == "pending-1"


def test_parse_filters_reject_unknown() -> None:
    with pytest.raises(EspnError, match="BANANAS"):
        parse_type_filters(["WAIVER", "BANANAS"])
    assert parse_type_filters(["waiver"]) == {"WAIVER"}
    assert parse_status_filters(["Pending", "EXECUTED"]) == {"PENDING", "EXECUTED"}
    with pytest.raises(EspnError, match="status"):
        parse_status_filters(["NOPE"])
