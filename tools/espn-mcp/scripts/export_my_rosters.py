"""Export the logged-in ESPN owner's current rosters across configured leagues.

Reads ESPN_S2 / ESPN_SWID from tools/espn-mcp/.env via espn_mcp.client.load_config.
Does not print cookie values. Writes a compact JSON + CSV snapshot under data/rosters/.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from espn_mcp.client import fetch, league_url, load_config, season_meta_url
from espn_mcp.rosters import (
    bye_map as _bye_map,
)
from espn_mcp.rosters import (
    normalize_player as _normalize_player,
)
from espn_mcp.rosters import (
    record_line as _record_line,
)
from espn_mcp.rosters import (
    round_stat as _round,
)
from espn_mcp.rosters import (
    sort_players as _sort_players,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
LEAGUES_PATH = REPO_ROOT / "apps/api/src/draft_api/data/espn_leagues.json"
DEFAULT_OUT_DIR = REPO_ROOT / "data/rosters"

def _load_leagues() -> list[dict[str, str]]:
    payload = json.loads(LEAGUES_PATH.read_text(encoding="utf-8"))
    return [{"id": str(item["id"]), "name": str(item["name"])} for item in payload]


def _member_record(member: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(member.get("id") or ""),
        "display_name": str(member.get("displayName") or ""),
        "first_name": str(member.get("firstName") or ""),
        "last_name": str(member.get("lastName") or ""),
    }


def _is_michael_doyle(member: dict[str, Any]) -> bool:
    first = str(member.get("firstName") or "").strip().lower()
    last = str(member.get("lastName") or "").strip().lower()
    display = str(member.get("displayName") or "").strip().lower()
    return (first == "michael" and last == "doyle") or display == "doyle.m"


def _owner_ids_to_export(members: list[dict[str, Any]], swid: str) -> dict[str, dict[str, str]]:
    """Cookie owner plus Michael Doyle when the ESPN session is a different account."""
    by_id: dict[str, dict[str, str]] = {}
    for member in members:
        record = _member_record(member)
        member_id = record["id"]
        if member_id and (member_id == swid or _is_michael_doyle(member)):
            by_id[member_id] = record
    if swid and swid not in by_id:
        by_id[swid] = {
            "id": swid,
            "display_name": "",
            "first_name": "",
            "last_name": "",
        }
    return by_id


def _team_owner_id(team: dict[str, Any], owner_ids: set[str]) -> str | None:
    primary = str(team.get("primaryOwner") or "")
    if primary in owner_ids:
        return primary
    for owner in team.get("owners") or []:
        owner_id = str(owner)
        if owner_id in owner_ids:
            return owner_id
    return None


async def _fetch_league(config, league_id: str) -> dict[str, Any]:
    payload = await fetch(
        league_url(config.season, league_id),
        config=config,
        views=["mTeam", "mRoster", "mStatus"],
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected ESPN payload for league {league_id}")
    return payload


async def export_rosters(out_dir: Path) -> dict[str, Any]:
    config = load_config()
    if not config.authenticated or not config.swid:
        raise SystemExit("ESPN_S2 and ESPN_SWID must be set in tools/espn-mcp/.env")

    season_meta = await fetch(
        season_meta_url(config.season),
        config=config,
        views=["proTeamSchedules_wl"],
    )
    bye_weeks = _bye_map(season_meta if isinstance(season_meta, dict) else {})

    leagues = _load_leagues()
    teams_out: list[dict[str, Any]] = []
    owners_out: dict[str, dict[str, str]] = {}
    scoring_period = None

    for league in leagues:
        payload = await _fetch_league(config, league["id"])
        scoring_period = payload.get("scoringPeriodId", scoring_period)
        owner_by_id = _owner_ids_to_export(payload.get("members") or [], config.swid)
        for owner_id, record in owner_by_id.items():
            public = {key: value for key, value in record.items() if key != "id"}
            if owner_id not in owners_out or not owners_out[owner_id].get("display_name"):
                owners_out[owner_id] = public
        for team in payload.get("teams") or []:
            owner_id = _team_owner_id(team, set(owner_by_id))
            if owner_id is None:
                continue
            owner = owner_by_id[owner_id]
            players = _sort_players(
                [
                    _normalize_player(entry, bye_weeks=bye_weeks)
                    for entry in ((team.get("roster") or {}).get("entries") or [])
                ]
            )
            teams_out.append(
                {
                    "league_id": league["id"],
                    "league_name": league["name"],
                    "team_id": int(team.get("id") or 0),
                    "team_name": str(team.get("name") or "").strip(),
                    "abbrev": str(team.get("abbrev") or ""),
                    "owner_display_name": owner.get("display_name") or "",
                    "owner_name": " ".join(
                        part for part in (owner.get("first_name"), owner.get("last_name")) if part
                    ).strip(),
                    "record": _record_line(team),
                    "points_for": _round(
                        (team.get("record") or {}).get("overall", {}).get("pointsFor")
                    ),
                    "projected_rank": team.get("currentProjectedRank"),
                    "waiver_rank": team.get("waiverRank"),
                    "player_count": len(players),
                    "players": players,
                }
            )

    snapshot = {
        "season": config.season,
        "scoring_period": scoring_period,
        "as_of": date.today().isoformat(),
        "source": "ESPN fantasy v3 mRoster",
        "owners": list(owners_out.values()),
        "team_count": len(teams_out),
        "player_count": sum(team["player_count"] for team in teams_out),
        "teams": teams_out,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "current-teams.json"
    csv_path = out_dir / "current-teams.csv"
    json_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    fieldnames = [
        "league_id",
        "league_name",
        "team_id",
        "team_name",
        "abbrev",
        "owner_display_name",
        "owner_name",
        "record",
        "espn_player_id",
        "player_name",
        "position",
        "nfl_team",
        "bye_week",
        "lineup_slot",
        "injury_status",
        "acquisition_type",
        "percent_owned",
        "percent_started",
        "fantasy_points",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for team in teams_out:
            for player in team["players"]:
                writer.writerow(
                    {
                        "league_id": team["league_id"],
                        "league_name": team["league_name"],
                        "team_id": team["team_id"],
                        "team_name": team["team_name"],
                        "abbrev": team["abbrev"],
                        "owner_display_name": team["owner_display_name"],
                        "owner_name": team["owner_name"],
                        "record": team["record"],
                        "espn_player_id": player["espn_player_id"],
                        "player_name": player["name"],
                        "position": player["position"],
                        "nfl_team": player["nfl_team"],
                        "bye_week": player["bye_week"],
                        "lineup_slot": player["lineup_slot"],
                        "injury_status": player["injury_status"],
                        "acquisition_type": player["acquisition_type"],
                        "percent_owned": player["percent_owned"],
                        "percent_started": player["percent_started"],
                        "fantasy_points": player["fantasy_points"],
                    }
                )

    snapshot["_files"] = {"json": str(json_path), "csv": str(csv_path)}
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    snapshot = asyncio.run(export_rosters(args.out_dir))
    print(
        json.dumps(
            {
                "as_of": snapshot["as_of"],
                "season": snapshot["season"],
                "scoring_period": snapshot["scoring_period"],
                "owners": snapshot["owners"],
                "team_count": snapshot["team_count"],
                "player_count": snapshot["player_count"],
                "teams": [
                    {
                        "league": team["league_name"],
                        "team": team["team_name"],
                        "owner": team["owner_display_name"] or team["owner_name"],
                        "record": team["record"],
                        "players": team["player_count"],
                    }
                    for team in snapshot["teams"]
                ],
                "files": snapshot["_files"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
