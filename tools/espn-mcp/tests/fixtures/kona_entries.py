"""Sanitized kona_player_info outer entries for contract tests."""

from __future__ import annotations

from typing import Any

WAIVER_ENTRY: dict[str, Any] = {
    "id": 2576623,
    "onTeamId": 0,
    "status": "WAIVERS",
    "waiverProcessDate": 1615993200000,
    "player": {
        "id": 2576623,
        "fullName": "DeVante Parker",
        "defaultPositionId": 3,
        "proTeamId": 15,
        "injuryStatus": "ACTIVE",
        "eligibleSlots": [3, 4, 5, 23, 7, 20, 21],
        "ownership": {
            "percentOwned": 82.49,
            "percentStarted": 40.0,
            "percentChange": 1.2,
        },
        "stats": [
            {
                "seasonId": 2020,
                "statSourceId": 0,
                "statSplitTypeId": 0,
                "scoringPeriodId": 0,
                "appliedTotal": 134.8,
                "appliedAverage": 9.63,
            },
            {
                "seasonId": 2020,
                "statSourceId": 1,
                "statSplitTypeId": 0,
                "scoringPeriodId": 0,
                "appliedTotal": 169.5,
            },
            {
                "seasonId": 2020,
                "statSourceId": 0,
                "statSplitTypeId": 1,
                "scoringPeriodId": 16,
                "appliedTotal": 12.4,
            },
            {
                "seasonId": 2019,
                "statSourceId": 0,
                "statSplitTypeId": 0,
                "scoringPeriodId": 0,
                "appliedTotal": 999.0,
            },
        ],
    },
}

ONTEAM_ENTRY: dict[str, Any] = {
    "id": 1,
    "onTeamId": 3,
    "status": "ONTEAM",
    "player": {
        "id": 1,
        "fullName": "Davante Adams",
        "defaultPositionId": 3,
        "proTeamId": 9,
        "injuryStatus": "ACTIVE",
        "stats": [],
    },
}

DST_ENTRY: dict[str, Any] = {
    "id": 99,
    "onTeamId": 0,
    "status": "WAIVERS",
    "player": {
        "id": 99,
        "fullName": "Seahawks D/ST",
        "defaultPositionId": 16,
        "proTeamId": 26,
        "stats": [],
    },
}

MINIMAL_ENTRY: dict[str, Any] = {
    "id": 42,
    "onTeamId": 0,
    "status": "FREEAGENT",
    "player": {
        "id": 42,
        "fullName": "Minimal Player",
        "defaultPositionId": 99,
        "proTeamId": 999,
    },
}
