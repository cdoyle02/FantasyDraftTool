"""Normalize ESPN mTransactions2 waiver / roster / trade activity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .client import EspnError
from .reference import LINEUP_SLOT_IDS
from .rosters import (
    member_index,
    owner_matches,
    owner_name,
    team_owned_by,
    team_owner,
)

KNOWN_TX_TYPES = frozenset({"WAIVER", "ROSTER", "TRADE", "FREEAGENT", "DRAFT"})
KNOWN_TX_STATUSES = frozenset({"PENDING", "EXECUTED", "CANCELED", "FAILED"})


def ms_to_iso(timestamp_ms: Any) -> str | None:
    if timestamp_ms is None or timestamp_ms == "":
        return None
    try:
        value = int(timestamp_ms)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat()


def lineup_slot_label(slot_id: Any) -> str | None:
    if slot_id is None or slot_id == "":
        return None
    try:
        raw = int(slot_id)
    except (TypeError, ValueError):
        return str(slot_id)
    if raw < 0:
        return None
    return LINEUP_SLOT_IDS.get(raw, str(raw))


def team_label(
    team_id: Any,
    *,
    team_names: dict[int, str],
) -> str:
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return "Unknown"
    if tid <= 0:
        return "Free Agency / Waivers"
    return team_names.get(tid, f"Team {tid}")


def normalize_item(
    item: dict[str, Any],
    *,
    team_names: dict[int, str],
    players: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    raw_player_id = item.get("playerId")
    try:
        player_id = int(raw_player_id) if raw_player_id is not None else None
    except (TypeError, ValueError):
        player_id = None
    player = players.get(player_id or -1, {})
    from_team_id = item.get("fromTeamId")
    to_team_id = item.get("toTeamId")
    from_slot = item.get("fromLineupSlotId")
    to_slot = item.get("toLineupSlotId")
    return {
        "type": str(item.get("type") or ""),
        "espn_player_id": player_id,
        "player_name": player.get("player_name") or player.get("name"),
        "position": player.get("position"),
        "nfl_team": player.get("pro_team") or player.get("nfl_team"),
        "from_team_id": from_team_id,
        "from_team": team_label(from_team_id, team_names=team_names),
        "to_team_id": to_team_id,
        "to_team": team_label(to_team_id, team_names=team_names),
        "from_lineup_slot_id": from_slot,
        "from_lineup_slot": lineup_slot_label(from_slot),
        "to_lineup_slot_id": to_slot,
        "to_lineup_slot": lineup_slot_label(to_slot),
        "is_keeper": bool(item.get("isKeeper")),
        "overall_pick_number": item.get("overallPickNumber") or None,
    }


def normalize_transaction(
    tx: dict[str, Any],
    *,
    league_id: str,
    league_name: str,
    team_names: dict[int, str],
    team_owners: dict[int, dict[str, str]],
    members: dict[str, dict[str, str]],
    players: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    try:
        team_id = int(tx.get("teamId") or 0)
    except (TypeError, ValueError):
        team_id = 0
    owner = team_owners.get(team_id) or {}
    member_id = str(tx.get("memberId") or "")
    member = members.get(member_id) or {}
    proposed_ms = tx.get("proposedDate")
    process_ms = tx.get("processDate") or tx.get("executionDate")
    return {
        "id": str(tx.get("id") or ""),
        "league_id": league_id,
        "league_name": league_name,
        "type": str(tx.get("type") or ""),
        "status": str(tx.get("status") or ""),
        "execution_type": str(tx.get("executionType") or ""),
        "is_pending": bool(tx.get("isPending")),
        "scoring_period_id": tx.get("scoringPeriodId"),
        "proposed_at": ms_to_iso(proposed_ms),
        "proposed_at_ms": proposed_ms,
        "processed_at": ms_to_iso(process_ms),
        "processed_at_ms": process_ms,
        "bid_amount": tx.get("bidAmount"),
        "sub_order": tx.get("subOrder"),
        "team_id": team_id or None,
        "team_name": team_names.get(team_id) if team_id else None,
        "owner_display_name": owner.get("display_name") or "",
        "owner_name": owner_name(owner),
        "member_id": member_id or None,
        "member_display_name": member.get("display_name") or "",
        "is_league_manager": bool(tx.get("isLeagueManager")),
        "is_acting_as_team_owner": bool(tx.get("isActingAsTeamOwner")),
        "items": [
            normalize_item(item, team_names=team_names, players=players)
            for item in (tx.get("items") or [])
            if isinstance(item, dict)
        ],
    }


def team_summary(team: dict[str, Any], *, members: dict[str, dict[str, str]]) -> dict[str, Any]:
    owner = team_owner(team, members)
    counter = team.get("transactionCounter") or {}
    return {
        "team_id": int(team.get("id") or 0),
        "team_name": str(team.get("name") or "").strip(),
        "abbrev": str(team.get("abbrev") or ""),
        "owner_display_name": owner.get("display_name") or "",
        "owner_name": owner_name(owner),
        "waiver_rank": team.get("waiverRank"),
        "is_transaction_locked": bool(team.get("isTransactionLocked")),
        "acquisitions": counter.get("acquisitions"),
        "drops": counter.get("drops"),
        "trades": counter.get("trades"),
        "move_to_active": counter.get("moveToActive"),
        "move_to_ir": counter.get("moveToIR"),
        "acquisition_budget_spent": counter.get("acquisitionBudgetSpent"),
        "matchup_acquisition_totals": counter.get("matchupAcquisitionTotals") or {},
    }


def waiver_status_summary(status: dict[str, Any]) -> dict[str, Any]:
    process = status.get("waiverProcessStatus") or {}
    runs = [
        {"at": key, "count": value}
        for key, value in sorted(process.items(), key=lambda pair: str(pair[0]))
    ]
    return {
        "transaction_scoring_period": status.get("transactionScoringPeriod"),
        "waiver_last_execution_at": ms_to_iso(status.get("waiverLastExecutionDate")),
        "waiver_last_execution_ms": status.get("waiverLastExecutionDate"),
        "is_waiver_order_edited": bool(status.get("isWaiverOrderEdited")),
        "recent_waiver_runs": runs,
    }


def parse_type_filters(raw: list[str] | None) -> set[str] | None:
    if not raw:
        return None
    values = {item.strip().upper() for item in raw if item and item.strip()}
    unknown = sorted(values - KNOWN_TX_TYPES)
    if unknown:
        known = ", ".join(sorted(KNOWN_TX_TYPES))
        raise EspnError(f"Unsupported transaction type(s) {unknown}. Known: {known}")
    return values


def parse_status_filters(raw: list[str] | None) -> set[str] | None:
    if not raw:
        return None
    values = {item.strip().upper() for item in raw if item and item.strip()}
    unknown = sorted(values - KNOWN_TX_STATUSES)
    if unknown:
        known = ", ".join(sorted(KNOWN_TX_STATUSES))
        raise EspnError(f"Unsupported transaction status(es) {unknown}. Known: {known}")
    return values


def transaction_matches(
    tx: dict[str, Any],
    *,
    types: set[str] | None,
    statuses: set[str] | None,
    scoring_period_id: int | None,
    pending_only: bool,
    team_id: int | None,
    owner_swid: str | None,
    owner_query: str | None,
    team_owners: dict[int, dict[str, str]],
    teams_by_id: dict[int, dict[str, Any]],
) -> bool:
    tx_type = str(tx.get("type") or "").upper()
    tx_status = str(tx.get("status") or "").upper()
    if types is not None and tx_type not in types:
        return False
    if statuses is not None and tx_status not in statuses:
        return False
    if pending_only and not bool(tx.get("isPending")):
        return False
    if scoring_period_id is not None and tx.get("scoringPeriodId") != scoring_period_id:
        return False
    try:
        tx_team_id = int(tx.get("teamId") or 0)
    except (TypeError, ValueError):
        tx_team_id = 0
    if team_id is not None and tx_team_id != team_id:
        return False
    team = teams_by_id.get(tx_team_id) or {}
    if owner_swid and team and not team_owned_by(team, owner_swid):
        return False
    if owner_query:
        owner = team_owners.get(tx_team_id) or {}
        if not owner_matches(owner, owner_query):
            return False
    return True


def collect_player_ids(transactions: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for tx in transactions:
        for item in tx.get("items") or []:
            if not isinstance(item, dict):
                continue
            raw = item.get("playerId")
            if raw is None:
                continue
            try:
                ids.add(int(raw))
            except (TypeError, ValueError):
                continue
    return ids


def build_team_indexes(
    payload: dict[str, Any],
) -> tuple[
    dict[int, str],
    dict[int, dict[str, str]],
    dict[int, dict[str, Any]],
    dict[str, dict[str, str]],
]:
    members = member_index(payload.get("members") or [])
    team_names: dict[int, str] = {}
    team_owners: dict[int, dict[str, str]] = {}
    teams_by_id: dict[int, dict[str, Any]] = {}
    for team in payload.get("teams") or []:
        try:
            tid = int(team.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if tid <= 0:
            continue
        teams_by_id[tid] = team
        team_names[tid] = str(team.get("name") or "").strip() or f"Team {tid}"
        team_owners[tid] = team_owner(team, members)
    return team_names, team_owners, teams_by_id, members


def normalize_transactions_payload(
    payload: dict[str, Any],
    *,
    league_id: str,
    league_name: str,
    players: dict[int, dict[str, Any]] | None = None,
    types: set[str] | None = None,
    statuses: set[str] | None = None,
    scoring_period_id: int | None = None,
    pending_only: bool = False,
    team_id: int | None = None,
    owner_swid: str | None = None,
    owner_query: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_team_summaries: bool = True,
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise EspnError(f"limit must be between 1 and 200, got {limit}")
    if offset < 0:
        raise EspnError(f"offset must be >= 0, got {offset}")

    team_names, team_owners, teams_by_id, members = build_team_indexes(payload)
    raw_txs = [tx for tx in (payload.get("transactions") or []) if isinstance(tx, dict)]
    filtered = [
        tx
        for tx in raw_txs
        if transaction_matches(
            tx,
            types=types,
            statuses=statuses,
            scoring_period_id=scoring_period_id,
            pending_only=pending_only,
            team_id=team_id,
            owner_swid=owner_swid,
            owner_query=owner_query,
            team_owners=team_owners,
            teams_by_id=teams_by_id,
        )
    ]
    # Newest first (ESPN usually returns newest-first already; enforce by proposedDate).
    filtered.sort(key=lambda tx: int(tx.get("proposedDate") or 0), reverse=True)
    window = filtered[offset : offset + limit]
    player_map = players or {}

    normalized = [
        normalize_transaction(
            tx,
            league_id=league_id,
            league_name=league_name,
            team_names=team_names,
            team_owners=team_owners,
            members=members,
            players=player_map,
        )
        for tx in window
    ]

    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
    result: dict[str, Any] = {
        "schema_version": 1,
        "league_id": league_id,
        "league_name": league_name,
        "scoring_period_id": payload.get("scoringPeriodId"),
        "total_transactions": len(raw_txs),
        "matched": len(filtered),
        "returned": len(normalized),
        "offset": offset,
        "limit": limit,
        "filters": {
            "types": sorted(types) if types is not None else None,
            "statuses": sorted(statuses) if statuses is not None else None,
            "scoring_period_id": scoring_period_id,
            "pending_only": pending_only,
            "team_id": team_id,
            "owner": owner_query,
            "mine": bool(owner_swid),
        },
        "waiver_status": waiver_status_summary(status),
        "transactions": normalized,
    }
    if include_team_summaries:
        summaries = [
            team_summary(team, members=members)
            for team in sorted(teams_by_id.values(), key=lambda row: int(row.get("id") or 0))
        ]
        if owner_swid:
            summaries = [
                row
                for row in summaries
                if team_owned_by(teams_by_id.get(row["team_id"]) or {}, owner_swid)
            ]
        if owner_query:
            summaries = [
                row
                for row in summaries
                if owner_matches(
                    {
                        "display_name": row.get("owner_display_name") or "",
                        "first_name": "",
                        "last_name": "",
                    },
                    owner_query,
                )
                or owner_query.strip().lower() in (row.get("owner_name") or "").lower()
                or owner_query.strip().lower() in (row.get("team_name") or "").lower()
            ]
        if team_id is not None:
            summaries = [row for row in summaries if row["team_id"] == team_id]
        result["team_summaries"] = summaries
    return result
