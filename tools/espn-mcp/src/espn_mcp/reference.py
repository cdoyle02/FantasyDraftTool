"""Static reference material for ESPN's undocumented fantasy football v3 API.

ESPN publishes no API documentation. Everything here was assembled from the
requests the fantasy web client makes, and it can change without notice.
"""

from __future__ import annotations

from typing import Any

READS_HOST = "https://lm-api-reads.fantasy.espn.com"

ENDPOINTS: list[dict[str, str]] = [
    {
        "name": "league",
        "path": "/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{league_id}",
        "use": "Primary endpoint for seasons 2018 and later. Combine with one or more views.",
        "auth": "Cookies required for private leagues.",
    },
    {
        "name": "league_history",
        "path": "/apis/v3/games/ffl/leagueHistory/{league_id}?seasonId={season}",
        "use": "Same views, for seasons 2017 and earlier. Returns a list, not an object.",
        "auth": "Cookies required for private leagues.",
    },
    {
        "name": "season_players",
        "path": "/apis/v3/games/ffl/seasons/{season}/players?scoringPeriodId=0&view=players_wl",
        "use": "League-independent player universe. Best source for an ESPN player id map.",
        "auth": "Public.",
    },
    {
        "name": "season_meta",
        "path": "/apis/v3/games/ffl/seasons/{season}",
        "use": "Season metadata. Add view=proTeamSchedules_wl for pro team schedules and byes.",
        "auth": "Public.",
    },
    {
        "name": "game_state",
        "path": "/apis/v3/games/ffl",
        "use": "Current scoring period and season status for the ffl game.",
        "auth": "Public.",
    },
]

VIEWS: list[dict[str, str]] = [
    {
        "view": "mDraftDetail",
        "returns": "draftDetail.picks[]",
        "use": (
            "Every draft pick with overallPickNumber, roundId, roundPickNumber, teamId, "
            "playerId, keeper and bidAmount. draftDetail.inProgress flags a live draft. "
            "This is the endpoint to poll for live draft sync."
        ),
    },
    {
        "view": "mSettings",
        "returns": "settings",
        "use": (
            "Roster slot counts (rosterSettings.lineupSlotCounts), scoring rules, draft type, "
            "keeper config and team count. Maps onto league configuration."
        ),
    },
    {
        "view": "mTeam",
        "returns": "teams[]",
        "use": "Team ids, names, owners, draft slot and record.",
    },
    {
        "view": "mRoster",
        "returns": "teams[].roster.entries[]",
        "use": "Current rostered players per team with lineupSlotId.",
    },
    {
        "view": "mMatchup",
        "returns": "schedule[]",
        "use": "Full season schedule with per-matchup team scores.",
    },
    {
        "view": "mMatchupScore",
        "returns": "schedule[].home/away.rosterForCurrentScoringPeriod",
        "use": "Adds per-player scoring detail to the schedule.",
    },
    {
        "view": "mScoreboard",
        "returns": "schedule[]",
        "use": "Scoreboard-oriented subset of matchup data.",
    },
    {
        "view": "mStandings",
        "returns": "teams[].record",
        "use": "Standings, streaks and points for/against.",
    },
    {
        "view": "mStatus",
        "returns": "status",
        "use": "Season state, current scoring period and transaction counts.",
    },
    {
        "view": "kona_player_info",
        "returns": "players[]",
        "use": (
            "Player pool with ownership, draft ranks and projections. Requires an "
            "X-Fantasy-Filter header to control limit, sorting and stat splits, otherwise "
            "the response is truncated or rejected."
        ),
    },
    {
        "view": "players_wl",
        "returns": "players[]",
        "use": "Lightweight league-independent player list. Used with the season_players path.",
    },
    {
        "view": "proTeamSchedules_wl",
        "returns": "settings.proTeams[]",
        "use": "Pro team schedules and bye weeks. Used with the season_meta path.",
    },
]

POSITION_IDS: dict[int, str] = {
    1: "QB",
    2: "RB",
    3: "WR",
    4: "TE",
    5: "K",
    16: "DST",
}

LINEUP_SLOT_IDS: dict[int, str] = {
    0: "QB",
    2: "RB",
    3: "RB/WR",
    4: "WR",
    5: "WR/TE",
    6: "TE",
    7: "OP",
    16: "DST",
    17: "K",
    20: "BENCH",
    21: "IR",
    23: "FLEX",
}

PRO_TEAM_IDS: dict[int, str] = {
    0: "FA",
    1: "ATL",
    2: "BUF",
    3: "CHI",
    4: "CIN",
    5: "CLE",
    6: "DAL",
    7: "DEN",
    8: "DET",
    9: "GB",
    10: "TEN",
    11: "IND",
    12: "KC",
    13: "LV",
    14: "LAR",
    15: "MIA",
    16: "MIN",
    17: "NE",
    18: "NO",
    19: "NYG",
    20: "NYJ",
    21: "PHI",
    22: "ARI",
    23: "PIT",
    24: "LAC",
    25: "SF",
    26: "SEA",
    27: "TB",
    28: "WSH",
    29: "CAR",
    30: "JAX",
    33: "BAL",
    34: "HOU",
}

NOTES: list[str] = [
    "ESPN has no official public API. Endpoints and payload shapes change without notice.",
    "Since April 2024 reads go to lm-api-reads.fantasy.espn.com, not fantasy.espn.com.",
    "Private leagues need the espn_s2 and SWID cookies from a logged-in browser session.",
    "SWID must keep its surrounding curly braces.",
    "Multiple views can be passed as repeated view query parameters.",
    "Draft picks carry playerId only, so names require a separate player map lookup.",
    "Projected season stats use stat id 10{season}, for example 102026. Actual use 00{season}.",
    "Select stats by seasonId, statSourceId, statSplitTypeId, and scoringPeriodId — not id alone.",
    "kona_player_info without X-Fantasy-Filter is truncated to about 50 players.",
    "Use espn_free_agents for league free agents and waiver players with verified filters.",
    "Full player payloads are megabytes. Prefer shape mode or a filtered limit while exploring.",
]

PLAYER_STATUSES: dict[str, str] = {
    "FREEAGENT": "Unrostered player available to add immediately.",
    "WAIVERS": "Player on waivers; add timing depends on league waiver rules.",
    "ONTEAM": "Player rostered by a fantasy team.",
}

FANTASY_FILTER_KEYS: dict[str, str] = {
    "filterStatus": "Restrict to availability statuses, e.g. FREEAGENT and WAIVERS.",
    "filterSlotIds": "Restrict to lineup slot ids (QB=0, RB=2, WR=4, TE=6, K=17, DST=16).",
    "limit": "Page size (live-verified up to 100 on kona_player_info).",
    "offset": "Page offset into the filtered player pool.",
    "sortPercOwned": "Sort by percent owned (sortPriority 1). Only verified sort for free agents.",
}


def stat_source_ids(season: int) -> dict[str, str]:
    """Return the composite stat split ids used inside player stat arrays."""
    return {
        "actual_season": f"00{season}",
        "projected_season": f"10{season}",
    }


def reference_document(season: int) -> dict[str, Any]:
    return {
        "season": season,
        "reads_host": READS_HOST,
        "endpoints": ENDPOINTS,
        "views": VIEWS,
        "position_ids": POSITION_IDS,
        "lineup_slot_ids": LINEUP_SLOT_IDS,
        "pro_team_ids": PRO_TEAM_IDS,
        "stat_split_ids": stat_source_ids(season),
        "player_statuses": PLAYER_STATUSES,
        "fantasy_filter_keys": FANTASY_FILTER_KEYS,
        "notes": NOTES,
    }
