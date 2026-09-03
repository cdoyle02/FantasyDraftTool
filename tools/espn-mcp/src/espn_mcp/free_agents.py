"""Core free-agent fetch and search orchestration (testable without MCP)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .filters import ESPN_SCAN_PAGE_SIZE, SEARCH_ROW_CAP, build_free_agent_filter
from .players import FreeAgentQuery, name_matches_search, normalize_player_entry

FetchPage = Callable[[int, int], Awaitable[list[dict[str, Any]]]]


@dataclass
class SearchScanResult:
    entries: list[dict[str, Any]]
    pages_scanned: int
    rows_scanned: int
    match_count: int
    status: str  # matched | exhausted | capped


async def fetch_kona_player_page(
    fetch_page: FetchPage,
    query: FreeAgentQuery,
    *,
    espn_limit: int,
    espn_offset: int,
) -> list[dict[str, Any]]:
    return await fetch_page(espn_offset, espn_limit)


async def scan_for_search_matches(
    fetch_page: FetchPage,
    query: FreeAgentQuery,
) -> SearchScanResult:
    """Scan 100-row ESPN pages until enough name matches or stop conditions hit."""
    assert query.search is not None
    matches: list[dict[str, Any]] = []
    espn_offset = 0
    pages_scanned = 0
    rows_scanned = 0
    capped = False
    exhausted = False
    target = query.offset + query.limit

    while len(matches) < target:
        if rows_scanned >= SEARCH_ROW_CAP:
            capped = True
            break

        page = await fetch_kona_player_page(
            fetch_page,
            query,
            espn_limit=ESPN_SCAN_PAGE_SIZE,
            espn_offset=espn_offset,
        )
        pages_scanned += 1
        if not page:
            exhausted = True
            break

        rows_scanned += len(page)
        for entry in page:
            player = entry.get("player") or entry
            name = player.get("fullName") or player.get("name") or ""
            if name_matches_search(name, query.search):
                matches.append(entry)

        if len(page) < ESPN_SCAN_PAGE_SIZE:
            exhausted = True
            break
        espn_offset += len(page)

    if capped:
        status = "capped"
    elif exhausted:
        status = "exhausted"
    else:
        status = "matched"

    return SearchScanResult(
        entries=matches[query.offset : query.offset + query.limit],
        pages_scanned=pages_scanned,
        rows_scanned=rows_scanned,
        match_count=len(matches),
        status=status,
    )


def build_page_filter(query: FreeAgentQuery, *, limit: int, offset: int) -> dict[str, Any]:
    return build_free_agent_filter(
        statuses=list(query.statuses),
        limit=limit,
        offset=offset,
        slot_ids=query.slot_ids,
        sort_by=query.sort_by,
        sort_asc=query.sort_asc,
    )


def normalize_entries(
    entries: list[dict[str, Any]],
    *,
    season: int,
    effective_scoring_period: int | None,
) -> list[dict[str, Any]]:
    return [
        normalize_player_entry(
            entry,
            season=season,
            scoring_period_id=effective_scoring_period,
        )
        for entry in entries
    ]


def effective_scoring_period(
    requested: int | None,
    payload: dict[str, Any],
) -> int | None:
    if requested is not None:
        return requested
    value = payload.get("scoringPeriodId")
    return value if isinstance(value, int) else None
