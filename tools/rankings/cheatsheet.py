"""Parse Fantasy Footballers cheatsheet CSV into official tiers and ADP.

Skill-position rows (QB/RB/WR/TE) with both tier_number and adp_overall become
overlay inputs. K/DST and incomplete rows are skipped so the existing board
keeps those positions.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

from merge import AdpRow, RankedPlayer, normalize_position, player_key

DEFAULT_CHEATSHEET = Path(__file__).resolve().parent / "data" / "footballers-cheatsheet-2026.csv"
_SKILL_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})


def cheatsheet_inputs(
    path: Path | None = None,
) -> tuple[dict[tuple[str, str], RankedPlayer], list[AdpRow]]:
    """Return name+position ranks/tiers and ADP rows for skill players."""
    cheatsheet = path or DEFAULT_CHEATSHEET
    if not cheatsheet.is_file():
        raise FileNotFoundError(f"Footballers cheatsheet not found: {cheatsheet}")

    ranked: dict[tuple[str, str], RankedPlayer] = {}
    adp_rows: list[AdpRow] = []
    with cheatsheet.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = _skill_row(row)
            if parsed is None:
                continue
            player, adp = parsed
            key = player_key(player.name, player.position)
            if key in ranked:
                continue
            ranked[key] = player
            adp_rows.append(adp)
    return ranked, adp_rows


def overlay_cheatsheet_tiers(
    grouped: Mapping[str, Sequence[RankedPlayer]],
    cheatsheet: Mapping[tuple[str, str], RankedPlayer],
) -> dict[str, list[RankedPlayer]]:
    """Stamp official cheatsheet tiers onto existing FPTS-ordered ranks."""
    result: dict[str, list[RankedPlayer]] = {}
    for position, rows in grouped.items():
        overlaid: list[RankedPlayer] = []
        for row in rows:
            cheat = cheatsheet.get(player_key(row.name, row.position))
            if cheat is None or cheat.tier is None:
                overlaid.append(row)
                continue
            overlaid.append(
                RankedPlayer(
                    name=row.name,
                    team=row.team,
                    position=row.position,
                    rank=row.rank,
                    tier=cheat.tier,
                )
            )
        result[position] = overlaid
    return result


def _skill_row(row: Mapping[str, str]) -> tuple[RankedPlayer, AdpRow] | None:
    position = normalize_position((row.get("position") or "").strip())
    if position not in _SKILL_POSITIONS:
        return None
    name = (row.get("player_name") or "").strip()
    if not name:
        return None
    rank = _positive_int(row.get("position_rank"))
    tier = _positive_int(row.get("tier_number"))
    adp = _positive_float(row.get("adp_overall"))
    if rank is None or tier is None or adp is None:
        return None
    team = (row.get("team") or "").strip().upper()
    ranked = RankedPlayer(name=name, team=team, position=position, rank=rank, tier=tier)
    return ranked, AdpRow(name=name, team=team, position=position, adp=adp)


def _positive_int(value: str | None) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except ValueError:
        return None
    return parsed if parsed >= 1 else None


def _positive_float(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
