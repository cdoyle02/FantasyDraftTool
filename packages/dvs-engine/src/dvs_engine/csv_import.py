"""FantasyPros-style CSV normalization using only the standard library."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .models import Player, Position

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("player", "player name", "name"),
    "position": ("pos", "position"),
    "team": ("team", "tm"),
    "projected_points": ("fpts", "fantasy points", "projected points", "projection", "points"),
    "adp": ("adp", "avg pick", "average draft position"),
    "tier": ("tier",),
    "id": ("id", "player id"),
}


@dataclass(frozen=True, slots=True)
class RowIssue:
    row: int
    field: str
    message: str


class CsvImportError(ValueError):
    def __init__(self, message: str, issues: tuple[RowIssue, ...] = ()) -> None:
        super().__init__(message)
        self.issues = issues


@dataclass(frozen=True, slots=True)
class ImportResult:
    players: tuple[Player, ...]
    warnings: tuple[RowIssue, ...] = ()


def import_players_csv(
    content: str,
    column_mapping: Mapping[str, str] | None = None,
    *,
    strict: bool = True,
) -> ImportResult:
    """Normalize CSV rows; user adjustments intentionally remain a separate layer."""
    if not content.strip():
        raise CsvImportError("CSV content is empty")
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise CsvImportError("CSV header is missing")
    mapping = _resolve_mapping(reader.fieldnames, column_mapping or {})
    missing = [field for field in ("name", "position", "projected_points") if field not in mapping]
    if missing:
        raise CsvImportError(f"missing required columns: {', '.join(missing)}")

    players: list[Player] = []
    issues: list[RowIssue] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        try:
            name = _value(row, mapping, "name")
            raw_position = _value(row, mapping, "position").upper()
            position = Position("DST" if raw_position in ("D/ST", "DEF", "D") else raw_position)
            team = _value(row, mapping, "team", required=False).upper()
            points = _number(_value(row, mapping, "projected_points"), "projected_points")
            adp_text = _value(row, mapping, "adp", required=False)
            tier_text = _value(row, mapping, "tier", required=False)
            supplied_id = _value(row, mapping, "id", required=False)
            player_id = supplied_id or _slug(f"{name}-{team}-{position.value}")
            if player_id in seen_ids:
                raise ValueError(f"duplicate player id '{player_id}'")
            player = Player(
                id=player_id,
                name=name,
                position=position,
                team=team,
                projected_points=points,
                adp=_number(adp_text, "adp") if adp_text else None,
                tier=int(float(tier_text)) if tier_text else 1,
            )
            players.append(player)
            seen_ids.add(player_id)
        except (KeyError, ValueError) as exc:
            issues.append(RowIssue(row_number, _issue_field(exc), str(exc)))
    if issues and strict:
        raise CsvImportError(f"{len(issues)} invalid CSV row(s)", tuple(issues))
    if not players:
        raise CsvImportError("CSV contains no valid player rows", tuple(issues))
    return ImportResult(tuple(players), tuple(issues))


def _resolve_mapping(
    fieldnames: Sequence[str], custom: Mapping[str, str]
) -> dict[str, str]:
    by_normalized = {_normalize_header(header): header for header in fieldnames}
    result: dict[str, str] = {}
    for field, header in custom.items():
        if field not in HEADER_ALIASES:
            raise CsvImportError(f"unknown target field '{field}'")
        if header not in fieldnames:
            raise CsvImportError(f"mapped column '{header}' does not exist")
        result[field] = header
    for field, aliases in HEADER_ALIASES.items():
        if field in result:
            continue
        for alias in aliases:
            if _normalize_header(alias) in by_normalized:
                result[field] = by_normalized[_normalize_header(alias)]
                break
    return result


def _value(
    row: Mapping[str, str | None],
    mapping: Mapping[str, str],
    field: str,
    *,
    required: bool = True,
) -> str:
    value = (row.get(mapping[field]) or "").strip() if field in mapping else ""
    if required and not value:
        raise ValueError(f"{field} is required")
    return value


def _number(value: str, field: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _issue_field(error: Exception) -> str:
    text = str(error)
    for field in HEADER_ALIASES:
        if field in text:
            return field
    return "row"
