"""FantasyPros official API client. I/O only; merge stays in merge.py."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any

from merge import POSITIONS, AdpRow, Projection, RankedPlayer, normalize_position

PUBLIC_BASE = "https://api.fantasypros.com/public/v2/json"
LEGACY_BASE = "https://api.fantasypros.com/v2/json"


class FantasyProsError(RuntimeError):
    pass


def api_key_from_env() -> str | None:
    key = os.environ.get("FANTASYPROS_API_KEY", "").strip()
    return key or None


def fetch_inputs(
    config: Mapping[str, Any],
    *,
    api_key: str,
    timeout: float = 30.0,
) -> tuple[
    list[Projection],
    dict[str, list[RankedPlayer]],
    dict[str, list[RankedPlayer]],
    list[AdpRow],
    dict[str, Any],
]:
    season = int(config["season"])
    scoring = str(config["scoring"])
    client = FantasyProsClient(api_key, timeout=timeout)
    resolved_experts: dict[str, list[dict[str, Any]]] = {}
    pooled: dict[str, list[RankedPlayer]] = {}
    consensus: dict[str, list[RankedPlayer]] = {}
    projections: list[Projection] = []
    adp_rows: list[AdpRow] = []

    for position in POSITIONS:
        configured = list(config.get("positions", {}).get(position, []))
        experts = client.resolve_experts(season, scoring, position, configured)
        resolved_experts[position] = experts
        filters = ":".join(str(item["id"]) for item in experts if item.get("id"))
        pooled[position] = client.consensus_rankings(season, scoring, position, filters=filters)
        consensus[position] = client.consensus_rankings(season, scoring, position)
        projections.extend(client.projections(season, scoring, position))
        adp_rows.extend(client.adp(season, scoring, position))

    return projections, pooled, consensus, adp_rows, resolved_experts


class FantasyProsClient:
    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def resolve_experts(
        self,
        season: int,
        scoring: str,
        position: str,
        configured: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        directory = self._expert_directory(season, scoring, position)
        resolved: list[dict[str, Any]] = []
        for entry in configured:
            expert_id = entry.get("id")
            name = str(entry.get("name", "")).strip()
            if not expert_id:
                expert_id = directory.get(_norm(name))
            if not expert_id:
                continue
            resolved.append(
                {
                    "name": name,
                    "id": int(expert_id),
                    "source": entry.get("source", ""),
                }
            )
        return resolved

    def consensus_rankings(
        self,
        season: int,
        scoring: str,
        position: str,
        *,
        filters: str = "",
    ) -> list[RankedPlayer]:
        params: dict[str, str] = {"position": position, "scoring": scoring, "week": "0"}
        if filters:
            params["filters"] = filters
        payload = self._get(f"/nfl/{season}/consensus-rankings", params)
        rows: list[RankedPlayer] = []
        for index, item in enumerate(_items(payload, "players"), start=1):
            name = _text(item, "player_name", "name")
            if not name:
                continue
            rows.append(
                RankedPlayer(
                    name=name,
                    team=_text(item, "player_team_id", "team_id", "team"),
                    position=normalize_position(
                        _text(item, "player_position_id", "position_id", "position") or position
                    ),
                    rank=_rank(item, index),
                    tier=_optional_int(item.get("tier")),
                )
            )
        return rows

    def projections(self, season: int, scoring: str, position: str) -> list[Projection]:
        payload = self._get(
            f"/nfl/{season}/projections",
            {"position": position, "scoring": scoring, "week": "0"},
        )
        rows: list[Projection] = []
        for item in _items(payload, "players"):
            name = _text(item, "name", "player_name")
            if not name:
                continue
            stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
            fpts = _projection_points(stats, scoring)
            if fpts is None:
                continue
            rows.append(
                Projection(
                    name=name,
                    team=_text(item, "team_id", "player_team_id", "team"),
                    position=normalize_position(
                        _text(item, "position_id", "player_position_id", "position") or position
                    ),
                    fpts=fpts,
                )
            )
        return rows

    def adp(self, season: int, scoring: str, position: str) -> list[AdpRow]:
        payload = self._get(
            f"/nfl/{season}/consensus-rankings",
            {"position": position, "scoring": scoring, "type": "ADP", "week": "0"},
        )
        rows: list[AdpRow] = []
        for index, item in enumerate(_items(payload, "players"), start=1):
            name = _text(item, "player_name", "name")
            if not name:
                continue
            adp = (
                _optional_float(item.get("rank_ave"))
                or _optional_float(item.get("rank_ecr"))
                or float(index)
            )
            rows.append(
                AdpRow(
                    name=name,
                    team=_text(item, "player_team_id", "team_id", "team"),
                    position=normalize_position(
                        _text(item, "player_position_id", "position_id", "position") or position
                    ),
                    adp=adp,
                )
            )
        return rows

    def _expert_directory(self, season: int, scoring: str, position: str) -> dict[str, int]:
        try:
            payload = self._get(
                f"/nfl/{season}/rankings/experts",
                {"position": position, "scoring": scoring},
            )
        except FantasyProsError:
            return {}
        directory: dict[str, int] = {}
        for item in _items(payload, "experts", "players"):
            name = _text(item, "expert_name", "name", "player_name")
            expert_id = item.get("expert_id", item.get("id"))
            if name and expert_id is not None:
                directory[_norm(name)] = int(expert_id)
        return directory

    def _get(self, path: str, params: Mapping[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        errors: list[str] = []
        for base in (PUBLIC_BASE, LEGACY_BASE):
            url = f"{base}{path}?{query}"
            request = urllib.request.Request(
                url,
                headers={"x-api-key": self.api_key, "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                errors.append(f"{base} -> HTTP {exc.code}")
                continue
            except urllib.error.URLError as exc:
                errors.append(f"{base} -> {exc.reason}")
                continue
            if isinstance(payload, dict):
                return payload
            errors.append(f"{base} -> unexpected payload")
        raise FantasyProsError(f"FantasyPros request failed for {path}: {'; '.join(errors)}")


def _items(payload: Mapping[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _text(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _rank(item: Mapping[str, Any], fallback: int) -> int:
    for key in ("rank_ecr", "rank", "pos_rank"):
        value = item.get(key)
        if value in (None, ""):
            continue
        match = re.search(r"\d+", str(value))
        if match:
            return int(match.group())
    return fallback


def _projection_points(stats: Mapping[str, Any], scoring: str) -> float | None:
    if scoring.upper() == "PPR":
        preferred = "points_ppr"
    elif "HALF" in scoring.upper():
        preferred = "points_half"
    else:
        preferred = "points"
    for key in (preferred, "points_ppr", "points", "fpts"):
        value = _optional_float(stats.get(key))
        if value is not None:
            return value
    return None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(value: str) -> str:
    return " ".join(value.lower().split())
