"""Inbox CSV reading and seed/CSV writers."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from merge import (
    POSITIONS,
    AdpRow,
    Projection,
    RankedPlayer,
    SeedPlayer,
    csv_rows,
    normalize_position,
)

_RANK_ALIASES = ("rank", "rk", "ecr", "pos rank", "pos_rank", "overall")
_TIER_ALIASES = ("tier",)
_NAME_ALIASES = ("player", "player name", "name")
_TEAM_ALIASES = ("team", "tm", "player_team_id")
_POS_ALIASES = ("pos", "position", "player_position_id")
_FPTS_ALIASES = ("fpts", "fantasy points", "projected points", "projection", "points", "points_ppr")
_ADP_ALIASES = ("adp", "avg pick", "average draft position", "rank_ecr", "avg")
_ESPN_ADP_ALIASES = ("espn adp", "espn", "adp espn")
_SLEEPER_ADP_ALIASES = ("sleeper adp", "sleeper", "adp sleeper")


def read_inbox(directory: Path) -> tuple[
    list[Projection],
    dict[str, list[RankedPlayer]],
    dict[str, list[RankedPlayer]],
    list[AdpRow],
    list[AdpRow],
    list[AdpRow],
]:
    if not directory.is_dir():
        raise FileNotFoundError(f"inbox directory does not exist: {directory}")
    files = {path.name.lower(): path for path in directory.glob("*.csv")}
    if not files:
        raise FileNotFoundError(f"inbox directory has no CSV files: {directory}")

    projections = _read_projections(_require_file(files, "projection"))
    adp_path = _find_file(files, "adp", exclude=("espn", "sleeper"))
    adp_rows = _read_adp(adp_path) if adp_path else []
    espn_path = _find_file(files, "espn-adp") or _find_file(files, "espn_adp")
    sleeper_path = _find_file(files, "sleeper-adp") or _find_file(files, "sleeper_adp")
    espn_rows = _read_adp(espn_path, platform_only=True) if espn_path else []
    sleeper_rows = _read_adp(sleeper_path, platform_only=True) if sleeper_path else []

    pooled: dict[str, list[RankedPlayer]] = {}
    consensus: dict[str, list[RankedPlayer]] = {}
    for position in POSITIONS:
        pooled_path = _find_file(files, f"rankings-{position.lower()}") or _find_file(
            files, f"{position.lower()}-rankings"
        )
        if pooled_path:
            pooled[position] = _read_rankings(pooled_path, position)
        consensus_path = _find_file(files, f"consensus-{position.lower()}")
        if consensus_path:
            consensus[position] = _read_rankings(consensus_path, position)

    if not pooled:
        raise FileNotFoundError(
            "inbox needs per-position rankings files named rankings-QB.csv through rankings-DST.csv"
        )
    return projections, pooled, consensus, adp_rows, espn_rows, sleeper_rows


def write_bundle(
    players: Sequence[SeedPlayer],
    json_path: Path,
    csv_path: Path,
    *,
    seed_version: str,
    experts: Mapping[str, Any],
    source: str,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seedVersion": seed_version,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "experts": experts,
        "players": [player.as_web_dict() for player in players],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Player", "Team", "POS", "FPTS", "ADP", "ESPN ADP", "Sleeper ADP", "Tier"],
        )
        writer.writeheader()
        writer.writerows(csv_rows(players))


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_file(files: Mapping[str, Path], token: str) -> Path:
    found = _find_file(files, token)
    if found is None:
        raise FileNotFoundError(f"inbox is missing a CSV whose name contains '{token}'")
    return found


def _find_file(
    files: Mapping[str, Path],
    token: str,
    *,
    exclude: Sequence[str] = (),
) -> Path | None:
    needle = token.lower()
    exact = files.get(f"{needle}.csv")
    if exact:
        return exact
    skipped = tuple(item.lower() for item in exclude)
    for name, path in files.items():
        if needle in name and not any(item in name for item in skipped):
            return path
    return None


def _read_projections(path: Path) -> list[Projection]:
    rows: list[Projection] = []
    for row in _dicts(path):
        name = _cell(row, _NAME_ALIASES)
        position = _cell(row, _POS_ALIASES)
        fpts = _number(_cell(row, _FPTS_ALIASES), "FPTS")
        if not name or not position:
            continue
        rank_text = _cell(row, ("consensus_rank", "consensus rank", "pos rank"))
        rows.append(
            Projection(
                name=name,
                team=_cell(row, _TEAM_ALIASES),
                position=normalize_position(position),
                fpts=fpts,
                consensus_rank=int(float(rank_text)) if rank_text else None,
            )
        )
    if not rows:
        raise ValueError(f"{path.name} contains no projection rows")
    return rows


def _read_rankings(path: Path, fallback_position: str) -> list[RankedPlayer]:
    rows: list[RankedPlayer] = []
    for index, row in enumerate(_dicts(path), start=1):
        name = _cell(row, _NAME_ALIASES)
        if not name:
            continue
        position = normalize_position(_cell(row, _POS_ALIASES) or fallback_position)
        rank_text = _cell(row, _RANK_ALIASES)
        rank = _parse_rank(rank_text, index)
        tier_text = _cell(row, _TIER_ALIASES)
        rows.append(
            RankedPlayer(
                name=name,
                team=_cell(row, _TEAM_ALIASES),
                position=position,
                rank=rank,
                tier=int(float(tier_text)) if tier_text else None,
            )
        )
    return rows


def _read_adp(path: Path, *, platform_only: bool = False) -> list[AdpRow]:
    rows: list[AdpRow] = []
    for row in _dicts(path):
        name = _cell(row, _NAME_ALIASES)
        position = _cell(row, _POS_ALIASES)
        adp_text = _cell(row, _ADP_ALIASES)
        if not name or not position or not adp_text:
            continue
        espn_text = "" if platform_only else _cell(row, _ESPN_ADP_ALIASES)
        sleeper_text = "" if platform_only else _cell(row, _SLEEPER_ADP_ALIASES)
        rows.append(
            AdpRow(
                name=name,
                team=_cell(row, _TEAM_ALIASES),
                position=normalize_position(position),
                adp=_number(adp_text, "ADP"),
                espn_adp=_number(espn_text, "ESPN ADP") if espn_text else None,
                sleeper_adp=_number(sleeper_text, "Sleeper ADP") if sleeper_text else None,
            )
        )
    return rows


def _dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _cell(row: Mapping[str, str], aliases: Sequence[str]) -> str:
    normalized = {_normalize_header(key): value for key, value in row.items() if key}
    for alias in aliases:
        value = normalized.get(_normalize_header(alias), "")
        if value:
            return value
    return ""


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _number(value: str, field: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc


def _parse_rank(value: str, fallback: int) -> int:
    if not value:
        return fallback
    match = re.search(r"\d+", value)
    return int(match.group()) if match else fallback
