"""Clay WR Out/Slot role resolution and nflverse stats filtering for SoS."""

from __future__ import annotations

import logging
from typing import Literal

from draft_api.sos.nflverse import HttpGetter, default_http_get
from draft_api.sos.snapshot import SnapshotError, read_packaged_snapshot
from draft_api.sos.usage import PlayerUsage
from draft_api.workbook.clay_pdf import ClayPdfError, load_clay_wr_rows
from draft_api.workbook.roles import Role, build_role_index, lookup_role, merge_last_known

logger = logging.getLogger("fantasy_draft_api.sos.clay_roles")

WrRole = Literal["all", "outside", "slot"]

_role_index_override: dict[str, Role] | None = None


def set_sos_clay_role_index_override(index: dict[str, Role] | None) -> None:
    """Test hook: inject Clay role map (None restores live/snapshot resolution)."""
    global _role_index_override
    _role_index_override = index


def parse_wr_role(value: str | None) -> WrRole:
    """Normalize API `wrRole` query param."""
    if value is None or value.strip() == "" or value.strip().lower() == "all":
        return "all"
    key = value.strip().lower()
    if key == "outside":
        return "outside"
    if key == "slot":
        return "slot"
    raise ValueError(f"wrRole must be all, outside, or slot (got {value!r})")


def ensure_wr_role_for_position(position: str, wr_role: WrRole) -> None:
    if wr_role != "all" and position != "WR":
        raise ValueError(
            f"wrRole applies to WR only (position={position!r}, wrRole={wr_role!r})"
        )


def filter_stats_by_clay_role(
    rows: list[dict[str, str | None]],
    role_index: dict[str, Role],
    wr_role: WrRole,
) -> list[dict[str, str | None]]:
    """Keep WR rows whose Clay role matches; `all` leaves rows unchanged."""
    if wr_role == "all":
        return rows
    filtered: list[dict[str, str | None]] = []
    for row in rows:
        row_pos = (row.get("position") or "").upper()
        if row_pos != "WR":
            filtered.append(row)
            continue
        name = (row.get("player_display_name") or row.get("player_name") or "").strip()
        role = lookup_role(role_index, name)
        if role is None:
            continue
        if role == wr_role:
            filtered.append(row)
    return filtered


def filter_usage_index_by_clay_role(
    usage: list[PlayerUsage],
    role_index: dict[str, Role],
    wr_role: WrRole,
) -> list[PlayerUsage]:
    """Opportunity table: only Clay-listed WRs matching the selected role."""
    if wr_role == "all":
        return usage
    out: list[PlayerUsage] = []
    for player in usage:
        if player.position != "WR":
            out.append(player)
            continue
        role = lookup_role(role_index, player.player_name)
        if role == wr_role:
            out.append(player)
    return out


def _workbook_packaged_clay_roles(season: int) -> dict[str, Role] | None:
    try:
        from draft_api.workbook.snapshot import read_packaged_snapshot as read_workbook

        wb = read_workbook(season)
        if wb.clay_roles:
            return wb.clay_roles
    except Exception as exc:  # noqa: BLE001 — optional fallback chain
        logger.debug("workbook clayRoles fallback unavailable: %s", exc)
    return None


def resolve_clay_role_index(
    season: int,
    *,
    http_get: HttpGetter | None = None,
    previous_clay_roles: dict[str, Role] | None = None,
    workbook_fallback: bool = True,
    role_index_override: dict[str, Role] | None = None,
) -> dict[str, Role]:
    """Live Clay PDF → merge previous (SoS snap) → optional workbook snap."""
    if role_index_override is not None:
        return role_index_override
    if _role_index_override is not None:
        return _role_index_override

    previous = dict(previous_clay_roles or ())
    if not previous:
        try:
            snap = read_packaged_snapshot(season)
            if snap.clay_roles:
                previous = dict(snap.clay_roles)
        except SnapshotError:
            pass

    if not previous and workbook_fallback:
        wb_roles = _workbook_packaged_clay_roles(season)
        if wb_roles:
            previous = dict(wb_roles)

    getter = http_get or default_http_get
    try:
        clay_rows = load_clay_wr_rows(season, http_get=getter)
        current = build_role_index(clay_rows)
        return merge_last_known(current, previous or None)
    except ClayPdfError as exc:
        logger.warning("Clay WR role sheet unavailable for SoS; using cached roles if any: %s", exc)
        return merge_last_known({}, previous or None)
