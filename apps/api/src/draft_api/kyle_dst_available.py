"""Join Kyle DST rankings to ESPN available defenses."""

from __future__ import annotations

from typing import Any

# ESPN uses WSH/JAX; FantasyPros / Odds API often use WAS/JAC.
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


def cross_ref_available(
    rankings: list[dict[str, Any]],
    available: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return Kyle-ordered rows that are FREEAGENT/WAIVERS in the league."""
    by_team: dict[str, dict[str, Any]] = {}
    for row in available:
        team = normalize_team(str(row.get("team") or ""))
        if team:
            by_team[team] = row
            alias = TEAM_ALIASES.get(team)
            if alias:
                by_team[alias] = row

    out: list[dict[str, Any]] = []
    for rank_row in rankings:
        team = normalize_team(str(rank_row.get("team") or ""))
        hit = by_team.get(team)
        if hit is None:
            continue
        out.append(
            {
                "rank": rank_row.get("rank"),
                "team": rank_row.get("team"),
                "teamName": rank_row.get("teamName"),
                "opponent": rank_row.get("opponent"),
                "ecr": rank_row.get("ecr"),
                "vsEcr": rank_row.get("vsEcr"),
                "status": hit.get("status"),
                "percentOwned": hit.get("percentOwned"),
            }
        )
    return out


def build_kyle_available_payload(
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
