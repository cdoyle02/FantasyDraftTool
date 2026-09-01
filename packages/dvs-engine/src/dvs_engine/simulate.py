"""Seeded one-turn opponent simulation for V4 survival and lookahead."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .formula import roster_shape_need, survival_probability
from .lookahead import MarginalCache
from .models import DraftState, FormulaParams, LeagueSettings, Player, Position
from .survival import per_pick_hazard


@dataclass(frozen=True, slots=True)
class OneTurnSimResult:
    survival_by_id: dict[str, float]
    fallback_by_id: dict[str, float]
    tier_exhaustion: dict[tuple[Position, int], float]
    expected_best: float
    path_survivors: tuple[frozenset[str], ...] = field(default_factory=tuple)
    intervening_count: int = 0


def _pick_weight(
    player: Player,
    pick_number: int,
    team_id: str,
    simulated_rosters: Mapping[str, tuple[str, ...]],
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
    current_round: int,
    run_pressure: Mapping[Position, float],
    params: FormulaParams,
) -> float:
    hazard = per_pick_hazard(player, pick_number, 1, params)
    roster = [
        players_by_id[player_id]
        for player_id in simulated_rosters.get(team_id, ())
        if player_id in players_by_id
    ]
    need = roster_shape_need(player.position, roster, settings, current_round)
    run = run_pressure.get(player.position, 1.0)
    return max(0.0, hazard * need * run)


def _sample_pick(
    rng: random.Random,
    remaining: Sequence[Player],
    pick_number: int,
    team_id: str,
    simulated_rosters: Mapping[str, tuple[str, ...]],
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
    current_round: int,
    run_pressure: Mapping[Position, float],
    params: FormulaParams,
    pool_size: int,
) -> Player | None:
    pool = sorted(
        remaining,
        key=lambda candidate: (candidate.adp or float("inf"), candidate.id),
    )[:pool_size]
    if not pool:
        return None
    weights = [
        _pick_weight(
            player,
            pick_number,
            team_id,
            simulated_rosters,
            players_by_id,
            settings,
            current_round,
            run_pressure,
            params,
        )
        for player in pool
    ]
    total = sum(weights)
    if total <= 0.0:
        return rng.choice(pool)
    threshold = rng.random() * total
    cumulative = 0.0
    for player, weight in zip(pool, weights, strict=True):
        cumulative += weight
        if cumulative >= threshold:
            return player
    return pool[-1]


def _best_same_position_fallback(
    player: Player,
    remaining_ids: frozenset[str],
    players_by_id: Mapping[str, Player],
    marginals: Mapping[str, float],
) -> float:
    best = 0.0
    for candidate_id in remaining_ids:
        if candidate_id == player.id:
            continue
        candidate = players_by_id.get(candidate_id)
        if candidate is None or candidate.position != player.position:
            continue
        best = max(best, marginals.get(candidate_id, 0.0))
    return best


def _best_pool_value(
    remaining_ids: frozenset[str],
    pool: Sequence[Player],
    marginals: Mapping[str, float],
    exclude_ids: frozenset[str] | None = None,
) -> float:
    excluded = exclude_ids or frozenset()
    best = 0.0
    for candidate in pool:
        if candidate.id not in remaining_ids or candidate.id in excluded:
            continue
        best = max(best, marginals.get(candidate.id, 0.0))
    return best


def _tier_keys(available: Sequence[Player]) -> set[tuple[Position, int]]:
    return {(player.position, player.tier) for player in available}


def _tier_exhaust_frequency(
    tier_key: tuple[Position, int],
    available: Sequence[Player],
    path_survivors: Sequence[frozenset[str]],
    intervening_count: int,
) -> float:
    position, tier = tier_key
    tier_member_ids = {
        player.id
        for player in available
        if player.position == position and player.tier == tier
    }
    if not tier_member_ids:
        return 0.0
    if len(tier_member_ids) > intervening_count:
        return 0.0
    exhausted = sum(
        1 for survivors in path_survivors if not tier_member_ids.intersection(survivors)
    )
    return exhausted / len(path_survivors)


def simulate_one_turn(
    available: Sequence[Player],
    marginals: Mapping[str, float],
    pool: Sequence[Player],
    schedule: Sequence[tuple[int, str]],
    state: DraftState,
    settings: LeagueSettings,
    players_by_id: Mapping[str, Player],
    current_round: int,
    run_pressure: Mapping[Position, float],
    params: FormulaParams,
) -> OneTurnSimResult:
    """Simulate opponent picks between user turns and aggregate joint outcomes."""
    intervening_count = len(schedule)
    available_ids = [player.id for player in available]
    if intervening_count == 0:
        all_survive = {player_id: 1.0 for player_id in available_ids}
        fallback = {
            player.id: _best_same_position_fallback(
                player, frozenset(available_ids), players_by_id, marginals
            )
            for player in available
        }
        survivors = frozenset(available_ids)
        expected_best = _best_pool_value(survivors, pool, marginals)
        tier_exhaust = {key: 0.0 for key in _tier_keys(available)}
        return OneTurnSimResult(
            survival_by_id=all_survive,
            fallback_by_id=fallback,
            tier_exhaustion=tier_exhaust,
            expected_best=expected_best,
            path_survivors=(survivors,),
            intervening_count=0,
        )

    num_sims = max(1, params.one_turn_sims)
    rng = random.Random(params.sim_seed)
    base_rosters = {team_id: tuple(players) for team_id, players in state.rosters.items()}
    path_survivors: list[frozenset[str]] = []

    for _ in range(num_sims):
        remaining = {player.id for player in available}
        simulated_rosters: dict[str, list[str]] = {
            team_id: list(players) for team_id, players in base_rosters.items()
        }
        for pick_number, team_id in schedule:
            remaining_players = [players_by_id[player_id] for player_id in remaining]
            picked = _sample_pick(
                rng,
                remaining_players,
                pick_number,
                team_id,
                simulated_rosters,
                players_by_id,
                settings,
                current_round,
                run_pressure,
                params,
                params.sim_pick_pool,
            )
            if picked is None:
                continue
            remaining.remove(picked.id)
            simulated_rosters.setdefault(team_id, []).append(picked.id)
        path_survivors.append(frozenset(remaining))

    survival_by_id = {
        player_id: sum(player_id in survivors for survivors in path_survivors) / num_sims
        for player_id in available_ids
    }
    fallback_by_id = {
        player.id: sum(
            _best_same_position_fallback(player, survivors, players_by_id, marginals)
            for survivors in path_survivors
        )
        / num_sims
        for player in available
    }
    expected_best = sum(
        _best_pool_value(survivors, pool, marginals) for survivors in path_survivors
    ) / num_sims
    tier_exhaust = {
        key: _tier_exhaust_frequency(key, available, path_survivors, intervening_count)
        for key in _tier_keys(available)
    }
    return OneTurnSimResult(
        survival_by_id=survival_by_id,
        fallback_by_id=fallback_by_id,
        tier_exhaustion=tier_exhaust,
        expected_best=expected_best,
        path_survivors=tuple(path_survivors),
        intervening_count=intervening_count,
    )


def next_pick_value_from_sim(
    drafted_player: Player,
    roster: Sequence[Player],
    pool: Sequence[Player],
    cache: MarginalCache,
    sim_result: OneTurnSimResult,
) -> float:
    """Expected best marginal at the next pick after drafting this player."""
    if not sim_result.path_survivors:
        return 0.0
    simulated = (*roster, drafted_player)
    marginals = {player.id: cache.marginal(player, simulated) for player in pool}
    exclude = frozenset({drafted_player.id})
    total = sum(
        _best_pool_value(survivors, pool, marginals, exclude_ids=exclude)
        for survivors in sim_result.path_survivors
    )
    return total / len(sim_result.path_survivors)


def adp_prior_survival(
    player: Player,
    current_pick: int,
    picks_until_next: int,
    intervening_count: int,
    params: FormulaParams,
) -> float:
    """ADP-based survival for breakdown display; 1.0 when no intervening opponent picks."""
    if intervening_count <= 0:
        return 1.0
    return survival_probability(player, current_pick, picks_until_next, params)
