"""Calibrated survival probabilities for the V4 decision engine."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence

from .formula import (
    expected_startable_slots,
    picks_until_team_turn,
    roster_shape_need,
    survival_probability,
)
from .models import DraftState, FormulaParams, LeagueSettings, Player, Position, team_on_clock


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def per_pick_hazard(
    player: Player,
    current_pick: int,
    picks_until_next: int,
    params: FormulaParams,
) -> float:
    """Convert ADP conditional survival into a per-pick hazard rate."""
    picks = max(1, picks_until_next)
    survival = survival_probability(player, current_pick, picks_until_next, params)
    survival = _clamp(survival, params.survival_clamp_low, params.survival_clamp_high)
    return 1.0 - math.pow(survival, 1.0 / picks)


def intervening_opponent_picks(
    state: DraftState,
    user_team_id: str,
    picks_until_next: int,
) -> list[str]:
    """Ordered team ids for each opponent selection before the user's next pick."""
    return [team_id for _, team_id in intervening_pick_schedule(state, user_team_id, picks_until_next)]


def intervening_pick_schedule(
    state: DraftState,
    user_team_id: str,
    picks_until_next: int,
) -> list[tuple[int, str]]:
    """Ordered (pick_number, team_id) for each opponent selection before the user's next pick."""
    if picks_until_next <= 0:
        return []
    user_on_clock = team_on_clock(state.current_pick, state.team_count) == user_team_id
    start_pick = state.current_pick + 1 if user_on_clock else state.current_pick
    end_pick = state.current_pick + picks_until_next
    schedule: list[tuple[int, str]] = []
    for pick_number in range(start_pick, end_pick):
        team_id = team_on_clock(pick_number, state.team_count)
        if team_id != user_team_id:
            schedule.append((pick_number, team_id))
    return schedule


def intervening_teams(state: DraftState, user_team_id: str, picks_until_next: int) -> list[str]:
    """Team ids drafting between the current pick and the user's next pick."""
    return intervening_opponent_picks(state, user_team_id, picks_until_next)


def opponent_need_multiplier(
    position: Position,
    team_id: str,
    state: DraftState,
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
    current_round: int,
) -> float:
    """Roster-shape need for one intervening team at a position."""
    roster = [
        players_by_id[player_id]
        for player_id in state.rosters.get(team_id, ())
        if player_id in players_by_id
    ]
    return roster_shape_need(position, roster, settings, current_round)


def run_pressure_by_position(
    state: DraftState,
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
    params: FormulaParams,
) -> dict[Position, float]:
    """Beta-binomial shrinkage on recent positional pick frequency."""
    window = max(1, params.run_window_picks)
    recent = state.pick_history[-window:]
    counts = Counter(
        players_by_id[pick.player_id].position
        for pick in recent
        if pick.player_id in players_by_id
    )
    total = sum(counts.values())
    startable = expected_startable_slots(settings)
    startable_total = sum(startable.values()) or 1.0
    pressure: dict[Position, float] = {}
    for position in (
        Position.QB,
        Position.RB,
        Position.WR,
        Position.TE,
        Position.K,
        Position.DST,
    ):
        expected_share = startable.get(position, 0.0) / startable_total
        observed = counts[position] / total if total else expected_share
        shrink = total / (total + params.run_prior_strength)
        excess = (observed - expected_share) * shrink
        if position in (Position.K, Position.DST) and not params.special_teams_run_pressure:
            pressure[position] = 1.0
        else:
            pressure[position] = 1.0 + params.run_weight * excess
    return pressure


def _demand_multiplier(
    player: Player,
    intervening: Sequence[str],
    state: DraftState,
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
    current_round: int,
    run_pressure: Mapping[Position, float],
    params: FormulaParams,
) -> float:
    if not intervening:
        return 1.0
    needs = [
        opponent_need_multiplier(
            player.position, team_id, state, players_by_id, settings, current_round
        )
        for team_id in intervening
    ]
    mean_need = sum(needs) / len(needs)
    run = run_pressure.get(player.position, 1.0)
    raw = mean_need * run
    weight = params.opponent_demand_weight_v4
    adjusted = 1.0 + weight * (raw - 1.0)
    return _clamp(adjusted, params.opponent_demand_min, params.opponent_demand_max)


def raw_adjusted_survival(
    player: Player,
    current_pick: int,
    intervening_count: int,
    intervening: Sequence[str],
    state: DraftState,
    players_by_id: Mapping[str, Player],
    settings: LeagueSettings,
    current_round: int,
    run_pressure: Mapping[Position, float],
    params: FormulaParams,
    picks_until_next: int,
) -> float:
    """Survival after per-pick hazard adjustment for intervening-team demand."""
    if intervening_count <= 0:
        return 1.0
    hazard = per_pick_hazard(player, current_pick, 1, params)
    demand = _demand_multiplier(
        player,
        intervening,
        state,
        players_by_id,
        settings,
        current_round,
        run_pressure,
        params,
    )
    per_pick_survival = 1.0 - _clamp(
        hazard * demand,
        0.0,
        1.0 - params.survival_clamp_low,
    )
    return math.pow(per_pick_survival, intervening_count)


def calibrate_survival_probabilities(
    raw_survivals: Mapping[str, float],
    intervening_picks: int,
    params: FormulaParams,
) -> dict[str, float]:
    """Scale survivals so expected players drafted equals intervening opponent picks."""
    if not params.survival_calibrate or intervening_picks <= 0:
        return dict(raw_survivals)
    target = float(intervening_picks)
    low = math.log(params.survival_clamp_low)
    high = math.log(1.0 / params.survival_clamp_low)

    def expected_drafted(log_lambda: float) -> float:
        scale = math.exp(log_lambda)
        return sum(1.0 - math.pow(s, scale) for s in raw_survivals.values())

    if expected_drafted(low) <= target <= expected_drafted(high):
        for _ in range(48):
            mid = (low + high) / 2.0
            if expected_drafted(mid) > target:
                high = mid
            else:
                low = mid
        scale = math.exp((low + high) / 2.0)
    else:
        scale = 1.0

    calibrated: dict[str, float] = {}
    for player_id, survival in raw_survivals.items():
        adjusted = math.pow(survival, scale)
        calibrated[player_id] = _clamp(
            adjusted, params.survival_clamp_low, params.survival_clamp_high
        )
    return calibrated


def compute_survival_maps(
    available: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    players_by_id: Mapping[str, Player],
    current_round: int,
    params: FormulaParams,
) -> tuple[
    dict[str, float],
    dict[str, float],
    dict[str, float],
    dict[str, float],
    dict[Position, float],
    list[tuple[int, str]],
    int,
]:
    """Return ADP prior, raw adjusted, calibrated survival, opponent need, run pressure, schedule."""
    until_next = picks_until_team_turn(state, settings.user_team_id)
    schedule = intervening_pick_schedule(state, settings.user_team_id, until_next)
    intervening = [team_id for _, team_id in schedule]
    intervening_count = len(intervening)
    run_pressure = run_pressure_by_position(state, players_by_id, settings, params)

    if intervening_count == 0:
        all_survive = {player.id: 1.0 for player in available}
        opponent_need = {player.id: 1.0 for player in available}
        return (
            dict(all_survive),
            dict(all_survive),
            dict(all_survive),
            opponent_need,
            run_pressure,
            schedule,
            intervening_count,
        )

    adp_prior: dict[str, float] = {}
    raw_adjusted: dict[str, float] = {}
    opponent_need: dict[str, float] = {}

    for player in available:
        adp_prior[player.id] = survival_probability(
            player, state.current_pick, until_next, params
        )
        opponent_need[player.id] = _demand_multiplier(
            player,
            intervening,
            state,
            players_by_id,
            settings,
            current_round,
            run_pressure,
            params,
        )
        raw_adjusted[player.id] = raw_adjusted_survival(
            player,
            state.current_pick,
            intervening_count,
            intervening,
            state,
            players_by_id,
            settings,
            current_round,
            run_pressure,
            params,
            until_next,
        )

    calibrated = calibrate_survival_probabilities(raw_adjusted, intervening_count, params)
    return adp_prior, raw_adjusted, calibrated, opponent_need, run_pressure, schedule, intervening_count
