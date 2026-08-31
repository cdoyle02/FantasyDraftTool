"""ESPN live-draft ADP (AVG PICK on fantasy.espn.com/football/livedraftresults)."""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from merge import AdpRow, normalize_position

READS_HOST = "https://lm-api-reads.fantasy.espn.com"
# PPR default board used by ESPN Live Draft Trends.
DEFAULT_SCORING_ID = 3
_POSITION_IDS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
_USER_AGENT = "Mozilla/5.0 (compatible; fantasy-draft-tool-rankings)"
SNAPSHOT = Path(__file__).resolve().parent / "data" / "espn-adp.csv"


def livedraft_url(season: int, scoring_id: int = DEFAULT_SCORING_ID) -> str:
    return (
        f"{READS_HOST}/apis/v3/games/ffl/seasons/{season}"
        f"/segments/0/leaguedefaults/{scoring_id}?view=kona_player_info"
    )


def livedraft_filter(limit: int = 800) -> dict[str, Any]:
    return {
        "players": {
            "limit": limit,
            "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "PPR"},
        }
    }


def fetch_espn_adp(
    *,
    season: int | None = None,
    league_id: str | None = None,
    timeout: float = 30.0,
) -> list[AdpRow]:
    """Return ESPN AVG PICK rows from Live Draft Trends, or a private league if set."""
    raw_season = season or int(os.environ.get("ESPN_SEASON", "2026") or "2026")
    resolved_league = (league_id or os.environ.get("ESPN_LEAGUE_ID", "")).strip() or None
    if resolved_league:
        url = (
            f"{READS_HOST}/apis/v3/games/ffl/seasons/{raw_season}"
            f"/segments/0/leagues/{resolved_league}?view=kona_player_info"
        )
    else:
        url = livedraft_url(raw_season)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "X-Fantasy-Filter": json.dumps(livedraft_filter(), separators=(",", ":")),
        },
    )
    cookies = _espn_cookie_header()
    if cookies:
        request.add_header("Cookie", cookies)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []
    if isinstance(payload, list):
        return espn_adp_rows(payload)
    if not isinstance(payload, dict):
        return []
    return espn_adp_rows(payload.get("players") or [])


def load_espn_adp(
    *,
    season: int | None = None,
    snapshot: Path = SNAPSHOT,
) -> list[AdpRow]:
    """Live fetch, then persist a snapshot. Fall back to the snapshot if ESPN is down."""
    rows = fetch_espn_adp(season=season)
    if rows:
        write_espn_snapshot(rows, snapshot)
        return rows
    return read_espn_snapshot(snapshot)


def write_espn_snapshot(rows: list[AdpRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Player", "Team", "POS", "ADP"])
        writer.writeheader()
        writer.writerows(
            {
                "Player": row.name,
                "Team": row.team,
                "POS": row.position,
                "ADP": f"{row.adp:.2f}",
            }
            for row in rows
        )


def read_espn_snapshot(path: Path) -> list[AdpRow]:
    if not path.is_file():
        return []
    rows: list[AdpRow] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("Player") or "").strip()
            position = (row.get("POS") or "").strip()
            adp_text = (row.get("ADP") or "").strip()
            if not name or not position or not adp_text:
                continue
            adp = _optional_float(adp_text)
            if adp is None:
                continue
            rows.append(
                AdpRow(
                    name=name,
                    team=(row.get("Team") or "").strip(),
                    position=normalize_position(position),
                    adp=adp,
                    espn_adp=adp,
                )
            )
    return rows


def espn_adp_from_player(player: Mapping[str, Any]) -> float | None:
    ownership = player.get("ownership") if isinstance(player.get("ownership"), dict) else {}
    adp = _optional_float(ownership.get("averageDraftPosition"))
    if adp is not None and adp > 0:
        return adp
    ranks = player.get("draftRanksByRankType") if isinstance(player.get("draftRanksByRankType"), dict) else {}
    ppr = ranks.get("PPR") if isinstance(ranks.get("PPR"), dict) else {}
    rank = _optional_float(ppr.get("rank"))
    if rank is not None and rank > 0:
        return rank
    return None


def espn_adp_rows(entries: list[Any]) -> list[AdpRow]:
    rows: list[AdpRow] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        player = entry.get("player") if isinstance(entry.get("player"), dict) else entry
        name = str(player.get("fullName") or player.get("name") or "").strip()
        position = _POSITION_IDS.get(player.get("defaultPositionId"), "")
        adp = espn_adp_from_player(player)
        if not name or not position or adp is None:
            continue
        rows.append(
            AdpRow(
                name=name,
                team=str(player.get("proTeam") or ""),
                position=normalize_position(position),
                adp=adp,
                espn_adp=adp,
            )
        )
    return rows


def _espn_cookie_header() -> str:
    parts: list[str] = []
    espn_s2 = os.environ.get("ESPN_S2", "").strip()
    swid = os.environ.get("ESPN_SWID", "").strip()
    if espn_s2:
        parts.append(f"espn_s2={espn_s2}")
    if swid:
        if not swid.startswith("{"):
            swid = "{" + swid.strip("{}") + "}"
        parts.append(f"SWID={swid}")
    return "; ".join(parts)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
