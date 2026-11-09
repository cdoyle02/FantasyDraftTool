"""Tier 2 opportunity fallback to packaged snap counts."""

from __future__ import annotations

from dataclasses import replace

from draft_api.sos.calculate import CompletedGame
from draft_api.sos.nflverse import NflverseError, SosDataset
from draft_api.sos.service import (
    build_tier2_opportunity_response,
    clear_sos_cache,
    set_sos_dataset_override,
    set_sos_http_get,
    set_sos_stats_rows_override,
)

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
    ],
    schedule={
        "AAA": {**{w: None for w in range(1, 19)}, 1: "BBB", 3: "BBB"},
        "BBB": {**{w: None for w in range(1, 19)}, 1: "AAA", 3: "AAA"},
    },
    teams=["AAA", "BBB"],
)

PACKAGED_SNAPS = (
    {
        "season": "2026",
        "week": "1",
        "game_type": "REG",
        "team": "AAA",
        "player": "Workhorse",
        "offense_pct": "0.80",
    },
)

PACKAGED_USAGE = (
    {
        "season": "2026",
        "week": "1",
        "season_type": "REG",
        "position": "RB",
        "team": "AAA",
        "opponent_team": "BBB",
        "player_id": "RB1",
        "player_display_name": "Workhorse",
        "carries": "20",
        "rushing_epa": "4",
    },
)


def setup_function() -> None:
    clear_sos_cache()
    set_sos_dataset_override(
        replace(FIXTURE, usage_stats=PACKAGED_USAGE, snap_counts=PACKAGED_SNAPS)
    )
    set_sos_stats_rows_override(list(PACKAGED_USAGE))


def teardown_function() -> None:
    set_sos_dataset_override(None)
    set_sos_stats_rows_override(None)
    set_sos_http_get(None)
    clear_sos_cache()


def test_tier2_opportunity_uses_packaged_snaps_when_live_fetch_fails() -> None:
    def _fail_snaps(url: str) -> bytes:
        if "snap_counts" in url:
            raise NflverseError("network down")
        raise NflverseError(f"unexpected url {url}")

    set_sos_http_get(_fail_snaps)
    body = build_tier2_opportunity_response(
        position="RB",
        window="season",
        week=3,
        season=2026,
    )
    assert body["snapFiltered"] is True
    assert len(body["players"]) >= 1
