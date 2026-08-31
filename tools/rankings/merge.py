"""Pure merge + rank-residual FPTS nudge. No network I/O."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")
_DST_ALIASES = {"D/ST", "DEF", "D", "DST"}


@dataclass(frozen=True, slots=True)
class RankedPlayer:
    name: str
    team: str
    position: str
    rank: int
    tier: int | None = None


@dataclass(frozen=True, slots=True)
class Projection:
    name: str
    team: str
    position: str
    fpts: float
    consensus_rank: int | None = None


@dataclass(frozen=True, slots=True)
class AdpRow:
    name: str
    team: str
    position: str
    adp: float
    espn_adp: float | None = None
    sleeper_adp: float | None = None


@dataclass(frozen=True, slots=True)
class SeedPlayer:
    id: str
    name: str
    position: str
    team: str
    projected_points: float
    adp: float
    tier: int
    espn_adp: float | None = None
    sleeper_adp: float | None = None

    def as_web_dict(self) -> dict[str, str | float | int]:
        data: dict[str, str | float | int] = {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "team": self.team,
            "projectedPoints": self.projected_points,
            "adp": self.adp,
            "tier": self.tier,
        }
        if self.espn_adp is not None:
            data["espnAdp"] = self.espn_adp
        if self.sleeper_adp is not None:
            data["sleeperAdp"] = self.sleeper_adp
        return data


@dataclass(frozen=True, slots=True)
class MergeConfig:
    k: float = 0.6
    nudge_clamp: float = 8.0
    missing_adp: float = 250.0
    gap_tier_threshold: int = 4


def normalize_position(value: str) -> str:
    raw = value.strip().upper()
    return "DST" if raw in _DST_ALIASES else raw


def normalize_name(value: str) -> str:
    text = value.lower()
    text = re.sub(r"\b(d/st|dst|defense|def)\b", "", text)
    text = re.sub(r"\b(jr|sr|iii|ii|iv)\b", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def player_key(name: str, position: str) -> tuple[str, str]:
    return (normalize_name(name), normalize_position(position))


def slug(name: str, team: str, position: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{name}-{team}-{position}".lower()).strip("-")


def merge_rankings(
    projections: Sequence[Projection],
    pooled: Mapping[str, Sequence[RankedPlayer]],
    *,
    consensus: Mapping[str, Sequence[RankedPlayer]] | None = None,
    adp_rows: Sequence[AdpRow] = (),
    espn_adp_rows: Sequence[AdpRow] = (),
    sleeper_adp_rows: Sequence[AdpRow] = (),
    config: MergeConfig | None = None,
) -> list[SeedPlayer]:
    """Build formulaV2 rows: market ADP, specialist-nudged FPTS, pooled/gap tiers."""
    settings = config or MergeConfig()
    pooled_index = _index_ranks(pooled)
    consensus_index = _index_ranks(consensus or {})
    adp_index = _index_adp(adp_rows)
    espn_index = _index_platform_adp(adp_rows, "espn_adp")
    espn_index.update(_index_adp(espn_adp_rows))
    sleeper_index = _index_platform_adp(adp_rows, "sleeper_adp")
    sleeper_index.update(_index_adp(sleeper_adp_rows))
    derived_consensus = _derived_consensus_ranks(projections)

    players: list[SeedPlayer] = []
    seen: set[str] = set()
    for projection in projections:
        position = normalize_position(projection.position)
        if position not in POSITIONS:
            continue
        key = player_key(projection.name, position)
        team = (projection.team or "").upper()
        player_id = slug(projection.name, team, position)
        if player_id in seen:
            continue
        consensus_entry = consensus_index.get(key)
        consensus_rank = _first_rank(
            projection.consensus_rank,
            consensus_entry[0] if consensus_entry else None,
            derived_consensus.get(key),
        )
        pooled_entry = pooled_index.get(key)
        pooled_rank = pooled_entry[0] if pooled_entry else consensus_rank
        nudge = settings.k * (consensus_rank - pooled_rank)
        nudge = max(-settings.nudge_clamp, min(settings.nudge_clamp, nudge))
        fpts = round(max(0.0, projection.fpts + nudge), 1)
        adp = adp_index.get(key, settings.missing_adp)
        if adp <= 0:
            adp = settings.missing_adp
        tier = _tier_for(pooled_entry, consensus_index.get(key))
        players.append(
            SeedPlayer(
                id=player_id,
                name=projection.name.strip(),
                position=position,
                team=team,
                projected_points=fpts,
                adp=float(adp),
                tier=tier,
                espn_adp=espn_index.get(key),
                sleeper_adp=sleeper_index.get(key),
            )
        )
        seen.add(player_id)

    _apply_gap_tiers(players, pooled_index, settings.gap_tier_threshold)
    players.sort(key=lambda item: (item.adp, -item.projected_points, item.name))
    return players


def gap_tiers(ranks: Sequence[int], threshold: int = 4) -> list[int]:
    """Assign tiers from a sorted positional rank list using rank gaps."""
    if not ranks:
        return []
    ordered = sorted(ranks)
    tiers = [1]
    for previous, current in zip(ordered, ordered[1:], strict=False):
        next_tier = tiers[-1] + 1 if current - previous >= threshold else tiers[-1]
        tiers.append(next_tier)
    by_rank = dict(zip(ordered, tiers, strict=False))
    return [by_rank[rank] for rank in ranks]


def _index_ranks(
    grouped: Mapping[str, Sequence[RankedPlayer]],
) -> dict[tuple[str, str], tuple[int, int | None]]:
    result: dict[tuple[str, str], tuple[int, int | None]] = {}
    for rows in grouped.values():
        for row in rows:
            key = player_key(row.name, row.position)
            current = result.get(key)
            if current is None or row.rank < current[0]:
                result[key] = (row.rank, row.tier)
    return result


def _index_adp(rows: Sequence[AdpRow]) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for row in rows:
        if row.adp <= 0:
            continue
        key = player_key(row.name, row.position)
        if key not in result:
            result[key] = row.adp
    return result


def _index_platform_adp(rows: Sequence[AdpRow], attr: str) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for row in rows:
        value = getattr(row, attr)
        if value is None or value <= 0:
            continue
        key = player_key(row.name, row.position)
        if key not in result:
            result[key] = float(value)
    return result


def _derived_consensus_ranks(projections: Sequence[Projection]) -> dict[tuple[str, str], int]:
    by_position: dict[str, list[Projection]] = {}
    for projection in projections:
        position = normalize_position(projection.position)
        by_position.setdefault(position, []).append(projection)
    ranks: dict[tuple[str, str], int] = {}
    for rows in by_position.values():
        ordered = sorted(rows, key=lambda item: (-item.fpts, item.name))
        for index, projection in enumerate(ordered, start=1):
            ranks[player_key(projection.name, projection.position)] = index
    return ranks


def _first_rank(*values: int | None) -> int:
    for value in values:
        if value is not None and value > 0:
            return int(value)
    return 1


def _tier_for(
    pooled: tuple[int, int | None] | None,
    consensus: tuple[int, int | None] | None,
) -> int:
    for entry in (pooled, consensus):
        if entry and entry[1] is not None and entry[1] >= 1:
            return entry[1]
    return 0


def _apply_gap_tiers(
    players: Sequence[SeedPlayer],
    pooled_index: Mapping[tuple[str, str], tuple[int, int | None]],
    threshold: int,
) -> None:
    missing = [player for player in players if player.tier < 1]
    if not missing:
        return
    by_position: dict[str, list[SeedPlayer]] = {}
    for player in missing:
        by_position.setdefault(player.position, []).append(player)
    for rows in by_position.values():
        decorated = [
            (
                player,
                pooled_index.get(player_key(player.name, player.position), (10_000, None))[0],
            )
            for player in rows
        ]
        decorated.sort(key=lambda item: item[1])
        assigned = gap_tiers([rank for _, rank in decorated], threshold)
        for (player, _), tier in zip(decorated, assigned, strict=True):
            object.__setattr__(player, "tier", tier)


def csv_rows(players: Iterable[SeedPlayer]) -> list[dict[str, str]]:
    return [
        {
            "Player": player.name,
            "Team": player.team,
            "POS": player.position,
            "FPTS": f"{player.projected_points:.1f}",
            "ADP": f"{player.adp:.1f}",
            "ESPN ADP": f"{player.espn_adp:.1f}" if player.espn_adp is not None else "",
            "Sleeper ADP": f"{player.sleeper_adp:.1f}" if player.sleeper_adp is not None else "",
            "Tier": str(player.tier),
        }
        for player in players
    ]
