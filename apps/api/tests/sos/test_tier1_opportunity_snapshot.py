"""Tier 1 opportunity fallback to packaged usage stats."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from draft_api.sos.calculate import CompletedGame
from draft_api.sos.nflverse import NflverseError, SosDataset
from draft_api.sos.service import (
    build_tier1_opportunity_response,
    clear_sos_cache,
    set_sos_dataset_override,
    set_sos_http_get,
    set_sos_stats_rows_override,
)
from draft_api.sos.snapshot import SnapshotError

FIXTURE = SosDataset(
    season=2026,
    fetched_at="2026-11-08T12:00:00Z",
    games=[
        CompletedGame(
            week=1,
            offense="AAA",
            defense="BBB",
            points={"QB": 0.0, "RB": 20.0, "WR": 0.0, "TE": 0.0, "DST": 0.0},
        ),
        CompletedGame(
            week=1,
            offense="BBB",
            defense="AAA",
            points={"QB": 0.0, "RB": 10.0, "WR": 0.0, "TE": 0.0, "DST": 0.0},
        ),
        CompletedGame(
            week=2,
            offense="AAA",
            defense="CCC",
            points={"QB": 0.0, "RB": 18.0, "WR": 0.0, "TE": 0.0, "DST": 0.0},
        ),
        CompletedGame(
            week=2,
            offense="CCC",
            defense="AAA",
            points={"QB": 0.0, "RB": 14.0, "WR": 0.0, "TE": 0.0, "DST": 0.0},
        ),
    ],
    schedule={
        "AAA": {**{w: None for w in range(1, 19)}, 1: "BBB", 2: "CCC", 3: "DDD"},
        "BBB": {**{w: None for w in range(1, 19)}, 1: "AAA", 2: "DDD", 3: "CCC"},
        "CCC": {**{w: None for w in range(1, 19)}, 1: "DDD", 2: "AAA", 3: "BBB"},
        "DDD": {**{w: None for w in range(1, 19)}, 1: "CCC", 2: "BBB", 3: "AAA"},
    },
    teams=["AAA", "BBB", "CCC", "DDD"],
)

PACKAGED_USAGE = (
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB1",
        "player_display_name": "Workhorse",
        "carries": "20",
    },
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB2",
        "player_display_name": "Change",
        "carries": "5",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB1",
        "player_display_name": "Workhorse",
        "carries": "18",
    },
    {
        "season": "2026",
        "week": "2",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "player_id": "RB2",
        "player_display_name": "Change",
        "carries": "6",
    },
)


def setup_function() -> None:
    clear_sos_cache()
    set_sos_dataset_override(replace(FIXTURE, usage_stats=PACKAGED_USAGE))


def teardown_function() -> None:
    set_sos_dataset_override(None)
    set_sos_stats_rows_override(None)
    set_sos_http_get(None)
    clear_sos_cache()


def test_opportunity_uses_dataset_usage_when_live_stats_fail() -> None:
    def _fail_stats(url: str) -> bytes:
        if "stats_player_week" in url:
            raise NflverseError("network down")
        raise NflverseError(f"unexpected url {url}")

    set_sos_http_get(_fail_stats)
    body = build_tier1_opportunity_response(
        position="RB",
        window="season",
        week=3,
        season=2026,
    )
    assert body.get("usageUnavailable") is not True
    assert len(body["players"]) >= 1
    workhorse = next(p for p in body["players"] if p["name"] == "Workhorse")
    assert workhorse["usageShare"] is not None


def test_opportunity_reads_packaged_usage_when_live_fetch_fails() -> None:
    set_sos_dataset_override(None)

    def _fail_nflverse(url: str) -> bytes:
        raise NflverseError(f"down: {url}")

    set_sos_http_get(_fail_nflverse)
    body = build_tier1_opportunity_response(
        position="RB",
        window="l8",
        week=10,
        season=2026,
    )
    assert body["stale"] is True
    assert body.get("usageUnavailable") is not True
    assert len(body["players"]) >= 1


@patch(
    "draft_api.sos.service.read_packaged_snapshot",
    side_effect=SnapshotError("no usage in package"),
)
def test_opportunity_marks_usage_unavailable_when_no_rows(_mock_snap: object) -> None:
    set_sos_dataset_override(FIXTURE)

    def _fail_stats(url: str) -> bytes:
        raise NflverseError("down")

    set_sos_http_get(_fail_stats)
    body = build_tier1_opportunity_response(
        position="RB",
        window="season",
        week=3,
        season=2026,
    )
    assert body["usageUnavailable"] is True
    assert body["players"] == []
