"""Monte Carlo convergence for V4 one-turn simulation."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace

import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Pick,
    Player,
    Position,
    apply_pick,
    team_on_clock,
)
from dvs_engine.formula import picks_until_team_turn
from dvs_engine.survival import intervening_opponent_picks
from dvs_engine.v4 import recommend_v4

TWELVE_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "SUPERFLEX": 0,
    "BENCH": 6,
    "K": 1,
    "DST": 1,
}

SEEDS = (7, 42, 99, 2026)
SIM_COUNTS = (48, 96, 192)
REFERENCE_SIMS = 480

TOLERANCE = {
    "survival": 0.15,
    "tier_exhaustion": 0.10,
    "next_pick": 1.0,
    "decision_score": 1.0,
}


@dataclass(frozen=True, slots=True)
class ConvergenceBoard:
    name: str
    state: DraftState
    settings: LeagueSettings
    pool: tuple[Player, ...]
    min_intervening: int


@dataclass(frozen=True, slots=True)
class ConvergenceMetrics:
    sims: int
    seed: int
    elapsed_ms: float
    top1_match: bool
    top3_match: bool
    max_survival_delta: float
    max_tier_exhaust_delta: float
    max_next_pick_delta: float
    max_score_delta: float


def _league(**overrides) -> LeagueSettings:
    base = {
        "team_count": 12,
        "roster_slots": TWELVE_SLOTS,
        "user_team_id": "6",
        "formula_params": FormulaParams(),
    }
    base.update(overrides)
    return LeagueSettings(**base)


def _build_pool() -> list[Player]:
    specs = {
        Position.QB: (320, 24, 0.8),
        Position.RB: (290, 60, 0.6),
        Position.WR: (285, 60, 0.6),
        Position.TE: (230, 30, 0.5),
        Position.K: (130, 20, 0.3),
        Position.DST: (125, 20, 0.3),
    }
    pool: list[Player] = []
    rank = 1
    for position, (top, count, step) in specs.items():
        for index in range(count):
            pool.append(
                Player(
                    id=f"{position.value.lower()}-{index + 1}",
                    name=f"{position.value} {index + 1}",
                    position=position,
                    projected_points=top - index * step,
                    adp=float(rank),
                    tier=max(1, 1 + index // 12),
                )
            )
            rank += 1
    return pool


def _snake_history(team_count: int, through_pick: int) -> tuple[Pick, ...]:
    return tuple(
        Pick(pick, team_on_clock(pick, team_count), f"ghost-{pick}")
        for pick in range(1, through_pick)
    )


def _user_roster_ids(rounds: int) -> tuple[str, ...]:
    return (
        "qb-1",
        "rb-1",
        "rb-2",
        "wr-1",
        "wr-2",
        "te-1",
        "rb-3",
    )


def _boards(pool: Sequence[Player]) -> list[ConvergenceBoard]:
    settings = _league()
    team_count = settings.team_count
    user = settings.user_team_id

    pick_one = DraftState(team_count=team_count)
    intervening_one = len(intervening_opponent_picks(pick_one, user, picks_until_team_turn(pick_one, user)))

    mid_pick = 78
    mid_state = DraftState(
        team_count=team_count,
        pick_history=_snake_history(team_count, mid_pick),
        reserved_rosters={user: _user_roster_ids(7)},
    )
    intervening_mid = len(
        intervening_opponent_picks(mid_state, user, picks_until_team_turn(mid_state, user))
    )

    penultimate_pick = (settings.rounds - 1) * team_count + int(user)
    pen_state = DraftState(
        team_count=team_count,
        pick_history=_snake_history(team_count, penultimate_pick),
        reserved_rosters={
            user: (
                "qb-1",
                "rb-1",
                "rb-2",
                "wr-1",
                "wr-2",
                "te-1",
                "rb-3",
                "rb-4",
                "wr-3",
                "wr-4",
                "rb-5",
                "wr-5",
                "rb-6",
            )
        },
    )
    intervening_pen = len(
        intervening_opponent_picks(pen_state, user, picks_until_team_turn(pen_state, user))
    )

    return [
        ConvergenceBoard("pick_1_empty", pick_one, settings, tuple(pool), intervening_one),
        ConvergenceBoard("mid_round_partial", mid_state, settings, tuple(pool), intervening_mid),
        ConvergenceBoard("penultimate_k_dst_open", pen_state, settings, tuple(pool), intervening_pen),
    ]


def _recommend(board: ConvergenceBoard, sims: int, seed: int):
    params = replace(board.settings.formula_params, one_turn_sims=sims, sim_seed=seed)
    settings = replace(board.settings, formula_params=params)
    started = time.perf_counter()
    results = recommend_v4(board.pool, board.state, settings, limit=20)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return results, elapsed_ms


def _compare(
    board: ConvergenceBoard,
    reference,
    candidate,
    sims: int,
    seed: int,
    elapsed_ms: float,
) -> ConvergenceMetrics:
    ref_top = [item.player_id for item in reference[:3]]
    cand_top = [item.player_id for item in candidate[:3]]
    ref_by_id = {item.player_id: item for item in reference}
    max_survival = 0.0
    max_tier = 0.0
    max_next = 0.0
    max_score = 0.0
    for player_id, ref_item in ref_by_id.items():
        cand_item = next((item for item in candidate if item.player_id == player_id), None)
        if cand_item is None:
            continue
        max_survival = max(
            max_survival,
            abs(
                cand_item.breakdown.adjusted_survival_probability
                - ref_item.breakdown.adjusted_survival_probability
            ),
        )
        max_tier = max(
            max_tier,
            abs(cand_item.breakdown.tier_exhaustion - ref_item.breakdown.tier_exhaustion),
        )
        max_next = max(
            max_next,
            abs(
                cand_item.breakdown.expected_next_pick_value
                - ref_item.breakdown.expected_next_pick_value
            ),
        )
        max_score = max(max_score, abs(cand_item.dvs_score - ref_item.dvs_score))
    return ConvergenceMetrics(
        sims=sims,
        seed=seed,
        elapsed_ms=elapsed_ms,
        top1_match=bool(reference) and bool(candidate) and reference[0].player_id == candidate[0].player_id,
        top3_match=ref_top == cand_top,
        max_survival_delta=max_survival,
        max_tier_exhaust_delta=max_tier,
        max_next_pick_delta=max_next,
        max_score_delta=max_score,
    )


def _passes(metrics: ConvergenceMetrics) -> bool:
    return (
        metrics.top1_match
        and metrics.top3_match
        and metrics.max_survival_delta <= TOLERANCE["survival"]
        and metrics.max_tier_exhaust_delta <= TOLERANCE["tier_exhaustion"]
        and metrics.max_next_pick_delta <= TOLERANCE["next_pick"]
        and metrics.max_score_delta <= TOLERANCE["decision_score"]
    )


def run_convergence_sweep() -> list[tuple[ConvergenceBoard, ConvergenceMetrics]]:
    pool = _build_pool()
    boards = _boards(pool)
    rows: list[tuple[ConvergenceBoard, ConvergenceMetrics]] = []
    for board in boards:
        assert board.min_intervening > 0, f"{board.name} has zero intervening picks"
        for seed in SEEDS:
            reference, _ = _recommend(board, REFERENCE_SIMS, seed)
            for sims in SIM_COUNTS:
                candidate, elapsed_ms = _recommend(board, sims, seed)
                rows.append(
                    (
                        board,
                        _compare(board, reference, candidate, sims, seed, elapsed_ms),
                    )
                )
    return rows


def format_sweep_report(rows: Sequence[tuple[ConvergenceBoard, ConvergenceMetrics]]) -> str:
    lines = ["Monte Carlo convergence sweep (reference=480 paths)", ""]
    current_board = ""
    for board, metrics in rows:
        if board.name != current_board:
            current_board = board.name
            lines.append(
                f"Board: {board.name} (intervening={board.min_intervening})"
            )
        lines.append(
            f"  sims={metrics.sims:3d} seed={metrics.seed:4d} "
            f"{metrics.elapsed_ms:6.0f}ms "
            f"top1={'OK' if metrics.top1_match else 'FAIL'} "
            f"top3={'OK' if metrics.top3_match else 'FAIL'} "
            f"dSurv={metrics.max_survival_delta:.2f} "
            f"dTier={metrics.max_tier_exhaust_delta:.2f} "
            f"dNext={metrics.max_next_pick_delta:.2f} "
            f"dScore={metrics.max_score_delta:.2f} "
            f"pass={'YES' if _passes(metrics) else 'no'}"
        )
    return "\n".join(lines)


def recommend_lowest_stable_sim_count(
    rows: Sequence[tuple[ConvergenceBoard, ConvergenceMetrics]],
) -> int:
    for sims in SIM_COUNTS:
        board_groups: dict[str, list[ConvergenceMetrics]] = {}
        for board, metrics in rows:
            if metrics.sims != sims:
                continue
            board_groups.setdefault(board.name, []).append(metrics)
        if all(all(_passes(item) for item in group) for group in board_groups.values()):
            return sims
    return SIM_COUNTS[-1]


@pytest.mark.slow
def test_simulation_convergence_against_reference():
    rows = run_convergence_sweep()
    report = format_sweep_report(rows)
    print("\n" + report)
    recommended = recommend_lowest_stable_sim_count(rows)
    print(f"\nLowest sim count passing all boards/seeds: {recommended}")
    pick_one_48 = [
        metrics
        for board, metrics in rows
        if board.name == "pick_1_empty" and metrics.sims == 48
    ]
    assert pick_one_48, "missing pick-1 sweep rows"
    assert all(item.top1_match and item.top3_match for item in pick_one_48)
    assert recommended == 48, (
        "48-path default failed convergence tolerances; review sweep report before raising default"
    )


@pytest.mark.slow
def test_convergence_boards_have_intervening_picks():
    pool = _build_pool()
    for board in _boards(pool):
        assert board.min_intervening > 0


@pytest.mark.slow
def test_pick_one_default_runtime_budget():
    pool = _build_pool()
    board = _boards(pool)[0]
    _, elapsed_ms = _recommend(board, FormulaParams().one_turn_sims, SEEDS[0])
    assert elapsed_ms < 1000, f"pick-1 recommend took {elapsed_ms:.0f}ms"
