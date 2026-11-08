"""Player-pool normalization, stat selection, and query validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from .client import EspnError
from .filters import DEFAULT_AVAILABILITY_STATUSES, POSITION_FILTER_SLOTS, SORT_DEFINITIONS
from .reference import POSITION_IDS, PRO_TEAM_IDS

AVAILABLE_STATUSES = frozenset({"FREEAGENT", "WAIVERS"})
POSITION_ALIASES = frozenset({"QB", "RB", "WR", "TE", "K", "DST", "D/ST", "DEF", "D"})
MIN_LIMIT = 1
MAX_LIMIT = 100


@dataclass(frozen=True)
class FreeAgentQuery:
    league_id: str
    season: int
    statuses: tuple[str, ...]
    position: str | None
    slot_ids: list[int] | None
    limit: int
    offset: int
    sort_by: Literal["percent_owned"]
    sort_asc: bool
    search: str | None
    scoring_period_id: int | None


def normalize_position_alias(value: str) -> str:
    raw = value.strip().upper()
    if raw in {"D/ST", "DEF", "D", "DST"}:
        return "DST"
    return raw


def is_available(status: str | None) -> bool:
    return status in AVAILABLE_STATUSES


ESPN_PROJECTION_LABEL = "ESPN projection, reference only"
ESPN_PROJECTION_NOTE = (
    "ESPN projections are reference only. "
    "A weekly answer quotes espn_projection.espn_projected_weekly_points and week. "
    "A season answer quotes espn_projection.espn_projected_season_points. "
    "null means ESPN sent no projection; do not invent one. "
    "0 is a real ESPN projection. Use injury_status on this object. "
    "Mention bye_week only when that key is present, because then it is this week. "
    "A team-total answer quotes espn_team_projection.espn_total_projected_points "
    "or espn_team_projection.espn_total_projected_points_live and names which field. "
    "Do not add player projections into a team total. "
    "Do not turn a higher projection into a start, sit, or add recommendation. "
    "Comparing two ESPN projection fields is allowed when the user asks which ESPN "
    "projection is higher; say the comparison is ESPN's projection. "
    "Do not combine these figures with Ballers, DST or kicker rankings, or odds. "
    "Name team_name from this same espn_projection object with the player. "
    "fantasy_points, weekly_actual_points, and season_actual_points are not projections."
)
PROJECTION_FLAG_TEXT = (
    "Pass include_projections=true only when the user asks for ESPN projections. "
    "Omitting it means the figures were not requested, not that ESPN has none."
)


def espn_projection_reference(
    stats: list[dict[str, Any]] | None,
    *,
    season: int,
    scoring_period: int | None,
    injury_status: str | None = None,
    bye_week: int | None = None,
    team_name: str | None = None,
    league_name: str | None = None,
) -> dict[str, Any]:
    """Quote ESPN's projected points without deriving a new number from them.

    statSourceId 1 is ESPN's projection. Split 0 is the season total. Split 1
    for the current scoring period is that week's projection. bye_week is included
    only when it is the same week as the projection.
    """
    season_row = select_stat(stats, season=season, source=1, split=0, scoring_period=0)
    week = scoring_period if scoring_period is not None and scoring_period >= 1 else None
    week_row = None
    if week is not None:
        week_row = select_stat(stats, season=season, source=1, split=1, scoring_period=week)
    quoted: dict[str, Any] = {
        "label": ESPN_PROJECTION_LABEL,
        "week": week,
        "espn_projected_weekly_points": _quoted_points(week_row),
        "espn_projected_season_points": _quoted_points(season_row),
        "injury_status": injury_status or None,
    }
    if week is not None and bye_week == week:
        quoted["bye_week"] = bye_week
    if team_name:
        quoted["team_name"] = team_name
    if league_name:
        quoted["league_name"] = league_name
    return quoted


def projection_envelope(week: int | None) -> dict[str, Any]:
    """One statement per tool result so the projection rule is not only on each player."""
    return {
        "source": "ESPN",
        "use": "reference_only",
        "week": week,
        "note": ESPN_PROJECTION_NOTE,
    }


def _quoted_points(stat: dict[str, Any] | None) -> float | None:
    if not stat or "appliedTotal" not in stat:
        return None
    value = stat.get("appliedTotal")
    if not isinstance(value, (int, float)):
        return None
    return round(float(value), 2)


def select_stat(
    stats: list[dict[str, Any]] | None,
    *,
    season: int,
    source: int,
    split: int,
    scoring_period: int,
) -> dict[str, Any] | None:
    for stat in stats or []:
        if (
            stat.get("seasonId") == season
            and stat.get("statSourceId") == source
            and stat.get("statSplitTypeId") == split
            and stat.get("scoringPeriodId") == scoring_period
        ):
            return stat
    return None


def _waiver_process_at(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _ownership_field(ownership: dict[str, Any] | None, key: str) -> float | None:
    if not ownership:
        return None
    value = ownership.get(key)
    return value if isinstance(value, (int, float)) else None


def normalize_player_entry(
    entry: dict[str, Any],
    *,
    season: int,
    scoring_period_id: int | None,
    include_legacy_projections: bool = False,
    include_full_stats: bool = True,
    include_projection_reference: bool = False,
) -> dict[str, Any]:
    """Normalize a kona_player_info outer player-pool entry."""
    player = entry.get("player") or entry
    outer_status = entry.get("status") if "player" in entry else None
    outer_on_team = entry.get("onTeamId") if "player" in entry else None
    waiver_ms = entry.get("waiverProcessDate") if "player" in entry else None

    name = player.get("fullName") or player.get("name") or ""
    position_id = player.get("defaultPositionId")
    pro_team_id = player.get("proTeamId")
    ownership = player.get("ownership") if isinstance(player.get("ownership"), dict) else None

    effective_period = scoring_period_id
    stats = player.get("stats") or []

    season_actual = None
    weekly_actual = None
    if include_full_stats:
        season_actual = select_stat(
            stats, season=season, source=0, split=0, scoring_period=0
        )
        if effective_period is not None and effective_period >= 1:
            weekly_actual = select_stat(
                stats,
                season=season,
                source=0,
                split=1,
                scoring_period=effective_period,
            )

    normalized: dict[str, Any] = {
        "player_id": player.get("id") or entry.get("id"),
        "name": name,
        "position": POSITION_IDS.get(position_id, "UNKNOWN"),
        "pro_team": PRO_TEAM_IDS.get(pro_team_id, "UNK"),
        "pro_team_id": pro_team_id,
        "status": outer_status,
        "on_team_id": outer_on_team,
        "is_available": is_available(outer_status),
        "eligible_slot_ids": player.get("eligibleSlots"),
        "percent_owned": _ownership_field(ownership, "percentOwned"),
        "percent_started": _ownership_field(ownership, "percentStarted"),
        "percent_change": _ownership_field(ownership, "percentChange"),
        "injury_status": player.get("injuryStatus"),
        "waiver_process_timestamp_ms": waiver_ms,
        "waiver_process_at": _waiver_process_at(waiver_ms),
    }

    if include_full_stats:
        normalized.update(
            {
                "season_actual_points": season_actual.get("appliedTotal")
                if season_actual
                else None,
                "season_average_points": season_actual.get("appliedAverage")
                if season_actual
                else None,
                "weekly_actual_points": weekly_actual.get("appliedTotal")
                if weekly_actual
                else None,
            }
        )

    # Quoted from ESPN's projection split. Nothing here is summed or scored again.
    if include_projection_reference:
        normalized["espn_projection"] = espn_projection_reference(
            stats,
            season=season,
            scoring_period=effective_period,
            injury_status=player.get("injuryStatus"),
        )
    if include_legacy_projections:
        ranks = player.get("draftRanksByRankType") or {}
        normalized["ppr_draft_rank"] = (ranks.get("PPR") or {}).get("rank")

    return normalized


def validate_free_agent_query(
    *,
    league_id: str | None,
    season: int,
    statuses: list[str] | None,
    position: str | None,
    limit: int,
    offset: int,
    sort_by: str,
    sort_asc: bool,
    scoring_period_id: int | None,
    search: str | None,
) -> FreeAgentQuery:
    if not league_id:
        raise EspnError(
            "No league id available. Pass league_id, or set ESPN_LEAGUE_ID in the MCP server "
            "environment. The id is the leagueId query parameter in a fantasy.espn.com URL."
        )
    if season < 1:
        raise EspnError(f"season must be a positive year, got {season}")

    resolved_statuses = tuple(statuses or DEFAULT_AVAILABILITY_STATUSES)
    if not resolved_statuses:
        raise EspnError("statuses must be non-empty")
    invalid = [value for value in resolved_statuses if value not in AVAILABLE_STATUSES]
    if invalid:
        raise EspnError(
            f"statuses must be FREEAGENT and/or WAIVERS for espn_free_agents, got {invalid}"
        )

    resolved_position: str | None = None
    slot_ids: list[int] | None = None
    if position is not None:
        resolved_position = normalize_position_alias(position)
        if resolved_position not in POSITION_FILTER_SLOTS:
            raise EspnError(
                f"position must be one of QB, RB, WR, TE, K, DST, D/ST, DEF, or D, got {position!r}"
            )
        slot_ids = [POSITION_FILTER_SLOTS[resolved_position]]

    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise EspnError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}, got {limit}")
    if offset < 0:
        raise EspnError(f"offset must be >= 0, got {offset}")
    if sort_by not in SORT_DEFINITIONS:
        raise EspnError(f"sort_by must be 'percent_owned', got {sort_by!r}")
    if scoring_period_id is not None and scoring_period_id < 0:
        raise EspnError(f"scoring_period_id must be >= 0, got {scoring_period_id}")

    cleaned_search = search.strip() if search else None
    if cleaned_search == "":
        cleaned_search = None

    return FreeAgentQuery(
        league_id=league_id,
        season=season,
        statuses=resolved_statuses,
        position=resolved_position,
        slot_ids=slot_ids,
        limit=limit,
        offset=offset,
        sort_by="percent_owned",
        sort_asc=sort_asc,
        search=cleaned_search,
        scoring_period_id=scoring_period_id,
    )


def name_matches_search(name: str, query: str) -> bool:
    return query.lower() in name.lower()


def pagination_fields(*, offset: int, limit: int, returned: int) -> dict[str, Any]:
    has_more = returned == limit
    return {
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "has_more": has_more,
        "next_offset": offset + returned if has_more else None,
    }
