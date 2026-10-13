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

from espn_mcp.client import EspnError, fetch, league_url, load_config, season_meta_url
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


def _is_katie_doyle(member: dict[str, Any]) -> bool:
    first = str(member.get("firstName") or "").strip().lower()
    last = str(member.get("lastName") or "").strip().lower()
    display = str(member.get("displayName") or "").strip().lower()
    return (first == "katie" and last == "doyle") or display in {
        "katie40890",
        "katie 40890",
    }


def _is_household_owner(member: dict[str, Any]) -> bool:
    """Michael + Katie Doyle household teams, regardless of which cookie is active."""
    return _is_michael_doyle(member) or _is_katie_doyle(member)


def _owner_ids_to_export(members: list[dict[str, Any]], swid: str) -> dict[str, dict[str, str]]:
    """Cookie owner plus household Doyle accounts when present in the league."""
    by_id: dict[str, dict[str, str]] = {}
    for member in members:
        record = _member_record(member)
        member_id = record["id"]
        if member_id and (member_id == swid or _is_household_owner(member)):
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


def _slug(text: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "league"


def _normalize_team_row(
    *,
    league: dict[str, str],
    team: dict[str, Any],
    owner: dict[str, str],
    bye_weeks: dict[int, int],
) -> dict[str, Any]:
    players = _sort_players(
        [
            _normalize_player(entry, bye_weeks=bye_weeks)
            for entry in ((team.get("roster") or {}).get("entries") or [])
        ]
    )
    return {
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
        "points_for": _round((team.get("record") or {}).get("overall", {}).get("pointsFor")),
        "projected_rank": team.get("currentProjectedRank"),
        "waiver_rank": team.get("waiverRank"),
        "player_count": len(players),
        "players": players,
    }


def _write_teams_csv(path: Path, teams: list[dict[str, Any]]) -> None:
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for team in teams:
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


async def export_rosters(out_dir: Path, *, full_leagues: bool = True) -> dict[str, Any]:
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
    league_files: list[str] = []
    skipped: list[dict[str, str]] = []

    leagues_dir = out_dir / "leagues"
    if full_leagues:
        leagues_dir.mkdir(parents=True, exist_ok=True)

    for league in leagues:
        try:
            payload = await _fetch_league(config, league["id"])
        except EspnError as error:
            # Cookie profile may not belong to every configured league (e.g. GWB vs Just The Tip).
            print(f"skip {league['name']} ({league['id']}): {error}")
            skipped.append({"league_id": league["id"], "league_name": league["name"], "error": str(error)})
            continue
        scoring_period = payload.get("scoringPeriodId", scoring_period)
        members = payload.get("members") or []
        member_index = {str(m.get("id") or ""): _member_record(m) for m in members if m.get("id")}
        owner_by_id = _owner_ids_to_export(members, config.swid)
        for owner_id, record in owner_by_id.items():
            public = {key: value for key, value in record.items() if key != "id"}
            if owner_id not in owners_out or not owners_out[owner_id].get("display_name"):
                owners_out[owner_id] = public

        league_teams: list[dict[str, Any]] = []
        for team in payload.get("teams") or []:
            primary = str(team.get("primaryOwner") or "")
            owner = member_index.get(primary) or {
                "display_name": "",
                "first_name": "",
                "last_name": "",
            }
            row = _normalize_team_row(
                league=league, team=team, owner=owner, bye_weeks=bye_weeks
            )
            league_teams.append(row)
            # Household snapshot: cookie owner + Michael/Katie Doyle.
            owner_id = _team_owner_id(team, set(owner_by_id))
            if owner_id is not None:
                teams_out.append(row)

        if full_leagues:
            league_snapshot = {
                "season": config.season,
                "scoring_period": scoring_period,
                "as_of": date.today().isoformat(),
                "source": "ESPN fantasy v3 mRoster (full league)",
                "league_id": league["id"],
                "league_name": league["name"],
                "team_count": len(league_teams),
                "player_count": sum(t["player_count"] for t in league_teams),
                "teams": league_teams,
            }
            league_path = leagues_dir / f"{league['id']}-{_slug(league['name'])}.json"
            league_path.write_text(json.dumps(league_snapshot, indent=2) + "\n", encoding="utf-8")
            league_files.append(str(league_path))
            print(f"wrote league {league['name']}: {len(league_teams)} teams -> {league_path.name}")

    snapshot = {
        "season": config.season,
        "scoring_period": scoring_period,
        "as_of": date.today().isoformat(),
        "source": "ESPN fantasy v3 mRoster (household Michael+Katie)",
        "owners": list(owners_out.values()),
        "team_count": len(teams_out),
        "player_count": sum(team["player_count"] for team in teams_out),
        "teams": teams_out,
        "skipped_leagues": skipped,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "current-teams.json"
    csv_path = out_dir / "current-teams.csv"
    json_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    _write_teams_csv(csv_path, teams_out)

    snapshot["_files"] = {
        "json": str(json_path),
        "csv": str(csv_path),
        "leagues": league_files,
    }
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--full-leagues",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also write data/rosters/leagues/<id>-<name>.json for every reachable league",
    )
    args = parser.parse_args()
    snapshot = asyncio.run(export_rosters(args.out_dir, full_leagues=args.full_leagues))
    print(
        json.dumps(
            {
                "as_of": snapshot["as_of"],
                "season": snapshot["season"],
                "scoring_period": snapshot["scoring_period"],
                "owners": snapshot["owners"],
                "team_count": snapshot["team_count"],
                "player_count": snapshot["player_count"],
                "skipped_leagues": snapshot.get("skipped_leagues") or [],
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
