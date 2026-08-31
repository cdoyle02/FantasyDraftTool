"""Parse Fantasy Footballers QB/FLEX comparison workbook into merge inputs.

Uses only the standard library (zipfile + ElementTree). The workbook provides
season counting stats for Mike, Andy, and Jason; we equal-weight average the
available analyst values and convert to season-total full PPR fantasy points.
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from merge import Projection, RankedPlayer, gap_tiers, normalize_position

NSM = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DEFAULT_WORKBOOK = Path(__file__).resolve().parent / "data" / "footballers-2026.xlsx"

# Expert stat blocks on comparison sheets (Mike, Andy, Jason).
_QB_EXPERT_BLOCKS: tuple[tuple[str, ...], ...] = (
    ("E", "F", "G", "H", "I", "J", "K", "L"),
    ("M", "N", "O", "P", "Q", "R", "S", "T"),
    ("U", "V", "W", "X", "Y", "Z", "AA", "AB"),
)
_FLEX_EXPERT_BLOCKS: tuple[tuple[str, ...], ...] = (
    ("E", "F", "G", "H", "I", "J", "K", "L", "M"),
    ("N", "O", "P", "Q", "R", "S", "T", "U", "V"),
    ("W", "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE"),
)

_SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})


@dataclass(frozen=True, slots=True)
class _SkillRow:
    name: str
    team: str
    position: str
    fpts: float


def footballers_inputs(
    path: Path | None = None,
    *,
    gap_tier_threshold: int = 4,
) -> tuple[list[Projection], dict[str, list[RankedPlayer]], dict[str, list[RankedPlayer]]]:
    """Return projections + pooled/consensus ranks for QB/RB/WR/TE."""
    workbook = path or DEFAULT_WORKBOOK
    if not workbook.is_file():
        raise FileNotFoundError(f"Footballers workbook not found: {workbook}")

    rows: list[_SkillRow] = []
    rows.extend(_parse_qb_comparison(_load_sheet(workbook, "QB Comparison")))
    rows.extend(_parse_flex_comparison(_load_sheet(workbook, "FLEX Comparison")))

    by_position: dict[str, list[_SkillRow]] = {}
    for row in rows:
        by_position.setdefault(row.position, []).append(row)

    projections: list[Projection] = []
    pooled: dict[str, list[RankedPlayer]] = {}
    consensus: dict[str, list[RankedPlayer]] = {}

    for position in ("QB", "RB", "WR", "TE"):
        ordered = sorted(by_position.get(position, []), key=lambda item: (-item.fpts, item.name))
        ranks = list(range(1, len(ordered) + 1))
        tiers = gap_tiers(ranks, gap_tier_threshold) if ranks else []
        for rank, tier, row in zip(ranks, tiers, ordered, strict=True):
            projections.append(
                Projection(
                    name=row.name,
                    team=row.team,
                    position=position,
                    fpts=round(row.fpts, 1),
                    consensus_rank=rank,
                )
            )
            ranked = RankedPlayer(
                name=row.name,
                team=row.team,
                position=position,
                rank=rank,
                tier=tier,
            )
            pooled.setdefault(position, []).append(ranked)
            consensus.setdefault(position, []).append(ranked)

    return projections, pooled, consensus


def ppr_season_points(
    *,
    pass_yds: float | None = None,
    pass_td: float | None = None,
    rush_yds: float | None = None,
    rush_td: float | None = None,
    rec: float | None = None,
    rec_yds: float | None = None,
    rec_td: float | None = None,
    ints: float | None = None,
    fum: float | None = None,
) -> float:
    """Standard full-PPR season fantasy points from counting stats."""
    total = 0.0
    if pass_yds is not None:
        total += pass_yds / 25.0
    if pass_td is not None:
        total += pass_td * 4.0
    if rush_yds is not None:
        total += rush_yds / 10.0
    if rush_td is not None:
        total += rush_td * 6.0
    if rec is not None:
        total += rec * 1.0
    if rec_yds is not None:
        total += rec_yds / 10.0
    if rec_td is not None:
        total += rec_td * 6.0
    if ints is not None:
        total += ints * -2.0
    if fum is not None:
        total += fum * -2.0
    return total


def _parse_qb_comparison(grid: dict[int, dict[str, str]]) -> list[_SkillRow]:
    rows: list[_SkillRow] = []
    for row_num in sorted(grid):
        if row_num < 6:
            continue
        row = grid[row_num]
        name = (row.get("A") or "").strip()
        if not name:
            continue
        team = (row.get("C") or "").strip().upper()
        stats = _average_qb_stats(row)
        if stats is None:
            continue
        fpts = ppr_season_points(**stats)
        rows.append(_SkillRow(name=name, team=team, position="QB", fpts=fpts))
    return rows


def _parse_flex_comparison(grid: dict[int, dict[str, str]]) -> list[_SkillRow]:
    rows: list[_SkillRow] = []
    for row_num in sorted(grid):
        if row_num < 6:
            continue
        row = grid[row_num]
        name = (row.get("A") or "").strip()
        position = normalize_position((row.get("B") or "").strip())
        if not name or position not in _SKILL_POSITIONS - {"QB"}:
            continue
        team = (row.get("C") or "").strip().upper()
        stats = _average_flex_stats(row)
        if stats is None:
            continue
        fpts = ppr_season_points(**stats)
        rows.append(_SkillRow(name=name, team=team, position=position, fpts=fpts))
    return rows


def _average_qb_stats(row: Mapping[str, str]) -> dict[str, float] | None:
    pass_yds = _average_expert_values(row, _QB_EXPERT_BLOCKS, (2,))
    pass_td = _average_expert_values(row, _QB_EXPERT_BLOCKS, (3,))
    rush_yds = _average_expert_values(row, _QB_EXPERT_BLOCKS, (4,))
    rush_td = _average_expert_values(row, _QB_EXPERT_BLOCKS, (5,))
    ints = _average_expert_values(row, _QB_EXPERT_BLOCKS, (6,))
    fum = _average_expert_values(row, _QB_EXPERT_BLOCKS, (7,))
    if all(value is None for value in (pass_yds, pass_td, rush_yds, rush_td, ints, fum)):
        return None
    return {
        "pass_yds": pass_yds or 0.0,
        "pass_td": pass_td or 0.0,
        "rush_yds": rush_yds or 0.0,
        "rush_td": rush_td or 0.0,
        "ints": ints or 0.0,
        "fum": fum or 0.0,
    }


def _average_flex_stats(row: Mapping[str, str]) -> dict[str, float] | None:
    rush_yds = _average_expert_values(row, _FLEX_EXPERT_BLOCKS, (3,))
    rush_td = _average_expert_values(row, _FLEX_EXPERT_BLOCKS, (4,))
    rec = _average_expert_values(row, _FLEX_EXPERT_BLOCKS, (5,))
    rec_yds = _average_expert_values(row, _FLEX_EXPERT_BLOCKS, (6,))
    rec_td = _average_expert_values(row, _FLEX_EXPERT_BLOCKS, (7,))
    fum = _average_expert_values(row, _FLEX_EXPERT_BLOCKS, (8,))
    if all(value is None for value in (rush_yds, rush_td, rec, rec_yds, rec_td, fum)):
        return None
    return {
        "rush_yds": rush_yds or 0.0,
        "rush_td": rush_td or 0.0,
        "rec": rec or 0.0,
        "rec_yds": rec_yds or 0.0,
        "rec_td": rec_td or 0.0,
        "fum": fum or 0.0,
    }


def _average_expert_values(
    row: Mapping[str, str],
    blocks: Sequence[tuple[str, ...]],
    stat_indexes: Iterable[int],
) -> float | None:
    values: list[float] = []
    for block in blocks:
        for index in stat_indexes:
            col = block[index]
            parsed = _num(row.get(col))
            if parsed is not None:
                values.append(parsed)
                break
    if not values:
        return None
    return sum(values) / len(values)


def _load_sheet(workbook: Path, sheet_name: str) -> dict[int, dict[str, str]]:
    with zipfile.ZipFile(workbook) as archive:
        target = _sheet_path(archive, sheet_name)
        return _grid_from_xml(archive.read(target))


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    wb = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    for sheet in wb.findall(NSM + "sheets/" + NSM + "sheet"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rid_to_target[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        return target
    raise ValueError(f"sheet not found: {sheet_name}")


def _grid_from_xml(payload: bytes) -> dict[int, dict[str, str]]:
    root = ET.fromstring(payload)
    rows: dict[int, dict[str, str]] = {}
    for cell in root.iter(NSM + "c"):
        ref = cell.attrib.get("r")
        if not ref:
            continue
        col, row = _col_row(ref)
        t = cell.attrib.get("t")
        value_node = cell.find(NSM + "v")
        inline = cell.find(NSM + "is")
        value: str | None
        if t == "inlineStr" and inline is not None:
            value = "".join(part.text or "" for part in inline.iter(NSM + "t"))
        elif value_node is not None and value_node.text is not None:
            value = value_node.text
        else:
            value = None
        if value is not None:
            rows.setdefault(row, {})[col] = value
    return rows


def _col_row(cell_ref: str) -> tuple[str, int]:
    match = re.match(r"([A-Z]+)(\d+)", cell_ref)
    if not match:
        raise ValueError(f"invalid cell ref: {cell_ref}")
    return match.group(1), int(match.group(2))


def _num(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None
