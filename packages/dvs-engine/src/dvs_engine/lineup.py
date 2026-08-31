"""Valid-lineup roster utility and marginal value for DVS v2."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

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

    slots = _user_slot_cap(settings)
    remaining = list(roster)
    utility = 0.0
    assigned: Counter[Position] = Counter()

    def consume(position: Position, count: int) -> None:
        nonlocal remaining, utility
        if count <= 0:
            return
        matches = [player for player in remaining if player.position == position]
        matches.sort(key=lambda player: player.projected_points, reverse=True)
        chosen = matches[:count]
        remaining = [player for player in remaining if player not in chosen]
        assigned[position] += len(chosen)
        utility += sum(_position_surplus(player, levels) for player in chosen)

    for position in DIRECT_POSITIONS:
        consume(position, slots[position.value])

    def _under_cap(player: Player) -> bool:
        if position_caps is None:
            return True
        cap = position_caps.get(player.position, _UNBOUNDED_CAP)
        return assigned[player.position] < cap

    flex_pool = [
        player
        for player in remaining
        if player.position in FLEX_ELIGIBLE and _under_cap(player)
    ]
    flex_pool.sort(key=lambda player: _position_surplus(player, levels), reverse=True)
    flex_taken = 0
    for player in flex_pool:
        if flex_taken >= slots["FLEX"]:
            break
        if not _under_cap(player):
            continue
        remaining.remove(player)
        assigned[player.position] += 1
        flex_taken += 1
        utility += _position_surplus(player, levels)

    superflex_pool = [
        player
        for player in remaining
        if player.position in SUPERFLEX_ELIGIBLE and _under_cap(player)
    ]
    superflex_pool.sort(key=lambda player: _position_surplus(player, levels), reverse=True)
    superflex_taken = 0
    for player in superflex_pool:
        if superflex_taken >= slots["SUPERFLEX"]:
            break
        if not _under_cap(player):
            continue
        remaining.remove(player)
        assigned[player.position] += 1
        superflex_taken += 1
        utility += _position_surplus(player, levels)

    bench_pool = sorted(
        remaining,
        key=lambda player: _position_surplus(player, levels),
        reverse=True,
    )
    bench_depth = Counter[str]()
    for player in bench_pool[: slots["BENCH"]]:
        bench_depth[player.position.value] += 1
        depth = bench_depth[player.position.value]
        utility += _bench_discount(params, depth) * _position_surplus(player, levels)

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
