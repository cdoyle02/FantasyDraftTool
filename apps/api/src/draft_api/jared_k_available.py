"""Join Jared Smola K rankings to ESPN available kickers."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# ESPN uses WSH/JAX; FantasyPros often uses WAS/JAC.
TEAM_ALIASES: dict[str, str] = {
    "JAC": "JAX",
    "JAX": "JAC",
    "WSH": "WAS",
    "WAS": "WSH",
}


def normalize_team(abbr: str | None) -> str:
    return (abbr or "").strip().upper()


def teams_match(a: str, b: str) -> bool:
    left = normalize_team(a)
    right = normalize_team(b)
    if not left or not right:
        return False
    if left == right:
        return True
    return TEAM_ALIASES.get(left) == right or TEAM_ALIASES.get(right) == left


def normalize_player_name(name: str | None) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def cross_ref_available(
    rankings: list[dict[str, Any]],
    available: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return Jared-ordered rows that are FREEAGENT/WAIVERS in the league."""
    by_name: dict[str, dict[str, Any]] = {}
    by_team: dict[str, list[dict[str, Any]]] = {}
    for row in available:
        name_key = normalize_player_name(str(row.get("name") or ""))
        if name_key:
            by_name[name_key] = row
        team = normalize_team(str(row.get("team") or ""))
        if team:
            by_team.setdefault(team, []).append(row)
            alias = TEAM_ALIASES.get(team)
            if alias:
                by_team.setdefault(alias, []).append(row)

    out: list[dict[str, Any]] = []
    for rank_row in rankings:
        player = str(rank_row.get("player") or "")
        hit = by_name.get(normalize_player_name(player))
        if hit is None:
            team = normalize_team(str(rank_row.get("team") or ""))
            team_hits = by_team.get(team) or []
            # Deduplicate alias double-inserts while preserving order.
            seen: set[int] = set()
            unique_hits: list[dict[str, Any]] = []
            for candidate in team_hits:
                key = id(candidate)
                if key in seen:
                    continue
                seen.add(key)
                unique_hits.append(candidate)
            if len(unique_hits) == 1:
                hit = unique_hits[0]
        if hit is None:
            continue
        out.append(
            {
                "rank": rank_row.get("rank"),
                "player": rank_row.get("player"),
                "team": rank_row.get("team"),
                "opponent": rank_row.get("opponent"),
                "ecr": rank_row.get("ecr"),
                "vsEcr": rank_row.get("vsEcr"),
                "status": hit.get("status"),
                "percentOwned": hit.get("percentOwned"),
            }
        )
    return out


def build_jared_available_payload(
    *,
    rankings_payload: dict[str, Any],
    available: list[dict[str, Any]],
    league: dict[str, str],
) -> dict[str, Any]:
    rankings = list(rankings_payload.get("rankings") or [])
    return {
        "week": rankings_payload.get("week"),
        "fetchedAt": rankings_payload.get("fetchedAt"),
        "sourceUrl": rankings_payload.get("sourceUrl"),
        "leagueId": league["id"],
        "leagueName": league["name"],
        "rankings": rankings,
        "available": cross_ref_available(rankings, available),
    }
