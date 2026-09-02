"""Valid-lineup roster utility and marginal value for DVS v2."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .models import FormulaParams, LeagueSettings, Player, Position

_UNBOUNDED_CAP = 10_000

FLEX_ELIGIBLE = (Position.RB, Position.WR, Position.TE)
SUPERFLEX_ELIGIBLE = (Position.QB, Position.RB, Position.WR, Position.TE)
DIRECT_POSITIONS = (
    Position.QB,
    Position.RB,
    Position.WR,
    Position.TE,
    Position.K,
    Position.DST,
)
STARTER_SLOT_LABELS = ("QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX")


@dataclass(frozen=True, slots=True)
class StarterFill:
    filled: int
    total: int
    open_slots: tuple[str, ...]


def _user_slot_cap(settings: LeagueSettings) -> dict[str, int]:
    slots = settings.roster_slots
    return {
        "QB": int(slots.get("QB", 0)),
        "RB": int(slots.get("RB", 0)),
        "WR": int(slots.get("WR", 0)),
        "TE": int(slots.get("TE", 0)),
        "FLEX": int(slots.get("FLEX", 0)),
        "SUPERFLEX": int(slots.get("SUPERFLEX", slots.get("SF", 0))),
        "BENCH": int(slots.get("BENCH", 0)),
        "K": int(slots.get("K", 0)),
        "DST": int(slots.get("DST", 0)),
    }


def _position_surplus(player: Player, levels: Mapping[Position, float]) -> float:
    return max(0.0, player.projected_points - levels.get(player.position, 0.0))


def _bench_discount(params: FormulaParams, depth: int) -> float:
    tiers = params.bench_discount_by_depth
    if depth <= 0:
        return params.bench_discount_default
    if depth <= len(tiers):
        return tiers[depth - 1]
    return tiers[-1] if tiers else params.bench_discount_default


def _under_cap(
    player: Player,
    assigned: Counter[Position],
    position_caps: Mapping[Position, int] | None,
) -> bool:
    if position_caps is None:
        return True
    cap = position_caps.get(player.position, _UNBOUNDED_CAP)
    return assigned[player.position] < cap


def _allocate_lineup(
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    params: FormulaParams,
    position_caps: Mapping[Position, int] | None = None,
) -> tuple[float, StarterFill]:
    """Assign starters and compute utility plus starter-slot occupancy."""
    slots = _user_slot_cap(settings)
    remaining = list(roster)
    utility = 0.0
    assigned: Counter[Position] = Counter()
    open_slots: list[str] = []

    def consume(position: Position, count: int, slot_label: str) -> None:
        nonlocal remaining, utility
        if count <= 0:
            return
        matches = [
            player
            for player in remaining
            if player.position == position and _under_cap(player, assigned, position_caps)
        ]
        matches.sort(key=lambda player: player.projected_points, reverse=True)
        chosen = matches[:count]
        if len(chosen) < count:
            open_slots.extend([slot_label] * (count - len(chosen)))
        remaining = [player for player in remaining if player not in chosen]
        assigned[position] += len(chosen)
        utility += sum(_position_surplus(player, levels) for player in chosen)

    for position in (Position.QB, Position.RB, Position.WR, Position.TE):
        consume(position, slots[position.value], position.value)

    flex_taken = 0
    flex_pool = [
        player
        for player in remaining
        if player.position in FLEX_ELIGIBLE and _under_cap(player, assigned, position_caps)
    ]
    flex_pool.sort(key=lambda player: _position_surplus(player, levels), reverse=True)
    for player in flex_pool:
        if flex_taken >= slots["FLEX"]:
            break
        remaining.remove(player)
        assigned[player.position] += 1
        flex_taken += 1
        utility += _position_surplus(player, levels)
    if flex_taken < slots["FLEX"]:
        open_slots.extend(["FLEX"] * (slots["FLEX"] - flex_taken))

    superflex_taken = 0
    superflex_pool = [
        player
        for player in remaining
        if player.position in SUPERFLEX_ELIGIBLE and _under_cap(player, assigned, position_caps)
    ]
    superflex_pool.sort(key=lambda player: _position_surplus(player, levels), reverse=True)
    for player in superflex_pool:
        if superflex_taken >= slots["SUPERFLEX"]:
            break
        remaining.remove(player)
        assigned[player.position] += 1
        superflex_taken += 1
        utility += _position_surplus(player, levels)
    if superflex_taken < slots["SUPERFLEX"]:
        open_slots.extend(["SUPERFLEX"] * (slots["SUPERFLEX"] - superflex_taken))

    starter_total = (
        slots["QB"]
        + slots["RB"]
        + slots["WR"]
        + slots["TE"]
        + slots["FLEX"]
        + slots["SUPERFLEX"]
    )
    starter_filled = starter_total - len(open_slots)
    starter_open_slots = tuple(open_slots)

    for position in (Position.K, Position.DST):
        consume(position, slots[position.value], position.value)

    bench_pool = sorted(
        remaining,
        key=lambda player: _position_surplus(player, levels),
        reverse=True,
    )
    bench_depth = Counter[str]()
    for player in bench_pool[: slots["BENCH"]]:
        if not _under_cap(player, assigned, position_caps):
            continue
        bench_depth[player.position.value] += 1
        depth = bench_depth[player.position.value]
        assigned[player.position] += 1
        utility += _bench_discount(params, depth) * _position_surplus(player, levels)

    fill = StarterFill(
        filled=starter_filled,
        total=starter_total,
        open_slots=starter_open_slots,
    )
    return utility, fill


def starter_slot_fill(
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    position_caps: Mapping[Position, int] | None = None,
) -> StarterFill:
    """Lineup-aware starter occupancy over non-K/DST starting slots."""
    _, fill = _allocate_lineup(
        roster,
        settings,
        levels,
        settings.formula_params,
        position_caps,
    )
    return fill


def roster_utility(
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    params: FormulaParams,
    position_caps: Mapping[Position, int] | None = None,
) -> float:
    """Starter assignment plus discounted bench value for the user's roster."""
    if not roster:
        return 0.0
    utility, _ = _allocate_lineup(roster, settings, levels, params, position_caps)
    return utility


def marginal_value(
    player: Player,
    roster: Sequence[Player],
    settings: LeagueSettings,
    levels: Mapping[Position, float],
    params: FormulaParams,
    position_caps: Mapping[Position, int] | None = None,
) -> float:
    """Change in roster utility from adding one player."""
    baseline = roster_utility(roster, settings, levels, params, position_caps)
    with_player = roster_utility((*roster, player), settings, levels, params, position_caps)
    return with_player - baseline
