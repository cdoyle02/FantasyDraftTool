"""ESPN FREEAGENT / WAIVERS D/ST fetch for Week D/ST cross-ref."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

ESPN_READ_HOST = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
DST_SLOT_ID = 16
K_SLOT_ID = 17

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


class EspnAvailableError(RuntimeError):
    """Raised when ESPN available-DST fetch fails."""


HttpJsonGetter = Callable[[str, dict[str, str]], Any]


def default_http_json(url: str, headers: dict[str, str]) -> Any:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise EspnAvailableError(f"ESPN HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise EspnAvailableError(f"ESPN request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise EspnAvailableError("ESPN returned invalid JSON") from exc


def fetch_available_players(
    *,
    league_id: str,
    season: int,
    slot_id: int,
    espn_s2: str | None = None,
    swid: str | None = None,
    statuses: list[str] | None = None,
    http_json: HttpJsonGetter | None = None,
    user_agent: str = "FantasyDraftTool-espn-available/1.0",
) -> list[dict[str, Any]]:
    """Return players for a lineup slot with FREEAGENT / WAIVERS status."""
    status_list = list(statuses or ["FREEAGENT", "WAIVERS"])
    fantasy_filter = {
        "players": {
            "filterStatus": {"value": status_list},
            "filterSlotIds": {"value": [slot_id]},
            "limit": 50,
            "offset": 0,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }
    query = urllib.parse.urlencode([("view", "kona_player_info")])
    url = f"{ESPN_READ_HOST}/seasons/{season}/segments/0/leagues/{league_id}?{query}"
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "X-Fantasy-Filter": json.dumps(fantasy_filter),
    }
    if espn_s2 and swid:
        headers["Cookie"] = f"espn_s2={espn_s2}; SWID={swid}"

    getter = http_json or default_http_json
    payload = getter(url, headers)
    if not isinstance(payload, dict):
        raise EspnAvailableError("ESPN returned an unexpected payload")

    rows: list[dict[str, Any]] = []
    for entry in payload.get("players") or []:
        if not isinstance(entry, dict):
            continue
        status = entry.get("status") or ""
        if status not in status_list:
            continue
        player = entry.get("player") or {}
        if not isinstance(player, dict):
            continue
        ownership = player.get("ownership") if isinstance(player.get("ownership"), dict) else {}
        pro_team_id = player.get("proTeamId")
        team = PRO_TEAM_IDS.get(int(pro_team_id), "UNK") if pro_team_id is not None else "UNK"
        rows.append(
            {
                "name": player.get("fullName") or "Unknown",
                "team": team,
                "status": status,
                "percentOwned": ownership.get("percentOwned"),
            }
        )
    rows.sort(
        key=lambda row: (
            -(row["percentOwned"] if isinstance(row["percentOwned"], (int, float)) else -1.0),
            str(row["name"]),
        )
    )
    return rows


def fetch_available_dst(
    *,
    league_id: str,
    season: int,
    espn_s2: str | None = None,
    swid: str | None = None,
    statuses: list[str] | None = None,
    http_json: HttpJsonGetter | None = None,
) -> list[dict[str, Any]]:
    """Return DST players with FREEAGENT / WAIVERS status for a league."""
    return fetch_available_players(
        league_id=league_id,
        season=season,
        slot_id=DST_SLOT_ID,
        espn_s2=espn_s2,
        swid=swid,
        statuses=statuses,
        http_json=http_json,
        user_agent="FantasyDraftTool-kyle-dst/1.0",
    )


def fetch_available_k(
    *,
    league_id: str,
    season: int,
    espn_s2: str | None = None,
    swid: str | None = None,
    statuses: list[str] | None = None,
    http_json: HttpJsonGetter | None = None,
) -> list[dict[str, Any]]:
    """Return kickers with FREEAGENT / WAIVERS status for a league."""
    return fetch_available_players(
        league_id=league_id,
        season=season,
        slot_id=K_SLOT_ID,
        espn_s2=espn_s2,
        swid=swid,
        statuses=statuses,
        http_json=http_json,
        user_agent="FantasyDraftTool-jared-k/1.0",
    )


def espn_credentials_from_env(
    *,
    league_id: str | None = None,
    espn_profile: str | None = None,
) -> tuple[str | None, str | None, int]:
    """Resolve ESPN cookies for a league (or explicit profile).

    Girls Who Ball uses Katie's ``ESPN_S2_KATIE`` / ``ESPN_SWID_KATIE`` pair;
    other leagues use Michael's ``ESPN_S2`` / ``ESPN_SWID``. Pass
    ``espn_profile='katie'|'michael'`` to override the league map.
    """
    from draft_api.espn_profiles import espn_credentials_for_profile, resolve_espn_profile

    try:
        profile = resolve_espn_profile(league_id, espn_profile)
    except ValueError as exc:
        raise EspnAvailableError(str(exc)) from exc
    return espn_credentials_for_profile(profile)
