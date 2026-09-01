"""V4 draft decision engine: one-turn lookahead with corrected wait-loss."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .formula import (
    effective_player,
    guardrail_adjustment,
    position_caps_map,
    replacement_levels,
    roster_shape_need,
    vorp,
)
from .lookahead import (
    MarginalCache,
    build_lookahead_pool,
    select_candidates,
    wait_loss_v4,
)
from .models import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    RecommendationBreakdown,
    RecommendationLabel,
    RecommendationResult,
    UserAdjustment,
)
from .simulate import adp_prior_survival, next_pick_value_from_sim, simulate_one_turn
from .survival import compute_survival_maps
from .tiers import (
    players_remaining_in_tier,
    tier_cliff,
    tier_opportunity_cost,
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def shape_adjustment(
    position: Position,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    params: FormulaParams,
) -> float:
    need = roster_shape_need(position, roster, settings, current_round)
    raw = params.need_points_scale * (need - 1.0)
    return _clamp(raw, -params.need_points_cap, params.need_points_cap)


def _reasons_v4(
    player: Player,
    marginal: float,
    player_vorp: float,
    wait_loss: float,
    survival: float,
    adjusted_survival: float,
    tier_cost: float,
    tier_remaining: int,
    tier_exhaust: float,
    cliff: float,
    next_value: float,
    shape: float,
    guardrail: float,
    adjustment: UserAdjustment | None,
    roster: Sequence[Player],
    settings: LeagueSettings,
    current_round: int,
    best_path: float,
    player_path: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if marginal > 0:
        reasons.append(f"{marginal:.1f} marginal roster points")
    if player_vorp > 0:
        reasons.append(f"{player_vorp:.1f} points above replacement")
    if tier_cost > 1.0 and cliff > 0:
        if tier_remaining <= 1:
            reasons.append(
                f"last remaining Tier-{player.tier} {player.position.value}"
            )
        else:
            reasons.append(f"Tier-{player.tier} {player.position.value} cliff of {cliff:.0f} pts")
    if adjusted_survival < 0.35:
        reasons.append(
            f"only {adjusted_survival * 100:.0f}% projected chance of surviving your next picks"
        )
    elif adjusted_survival > 0.65:
        reasons.append("likely available at your next pick")
    if wait_loss >= 4:
        reasons.append("meaningful expected loss if you wait")
    if next_value > 0:
        reasons.append(f"{next_value:.1f} expected value from your next pick after this choice")
    if player_path >= best_path - 0.5 and player_path > marginal + 5:
        reasons.append("best expected two-pick roster outcome")
    counts = Counter(item.position for item in roster)
    direct = int(settings.roster_slots.get(player.position.value, 0))
    if shape > 3:
        if counts[player.position] < direct:
            reasons.append("fills an open starter slot")
        else:
            reasons.append("fills a roster need")
    elif shape < -3:
        reasons.append("position already filled")
    if shape < 0 and marginal >= 10 and player_path >= best_path - 1.0:
        reasons.append("elite value overrides roster need")
    if guardrail < 0:
        reasons.append("deprioritized by roster guardrails")
    if player.position == Position.TE and counts[Position.TE] >= settings.formula_params.max_te:
        reasons.append("roster already has a TE")
    if player.position == Position.QB:
        cap = settings.formula_params.max_qb + int(
            settings.roster_slots.get("SUPERFLEX", settings.roster_slots.get("SF", 0))
        )
        if counts[Position.QB] >= cap:
            late_window = (
                settings.team_count >= settings.formula_params.backup_qb_min_team_count
                and current_round
                > settings.rounds - settings.formula_params.backup_qb_final_rounds
            )
            if late_window:
                reasons.append("backup QB only late")
    if adjustment and adjustment.tag:
        reasons.append(f"user tag: {adjustment.tag}")
    if tier_exhaust > 0.5 and tier_cost > 0:
        reasons.append("tier unlikely to survive to your next pick")
    return tuple(reasons)


@dataclass(frozen=True, slots=True)
class _DraftRow:
    player: Player
    player_vorp: float
    marginal: float
    survival: float
    adjusted_survival: float
    fallback: float
    loss: float
    cliff: float
    tier_remaining: int
    tier_exhaust: float
    tier_cost: float
    next_value: float
    need: float
    shape: float
    guardrail: float
    adjustment: UserAdjustment | None
    opinion: float
    decision_score: float
    two_pick_path: float
    run: float
    opponent_need: float


def recommend_v4(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None = None,
    limit: int = 20,
) -> list[RecommendationResult]:
    params = settings.formula_params
    adjustments = adjustments or {}
    drafted_ids = state.drafted_ids
    adjusted_all = [effective_player(player, adjustments.get(player.id)) for player in players]
    available = [player for player in adjusted_all if player.id not in drafted_ids]
    if params.exclude_avoid_tag:
        available = [
            player
            for player in available
            if adjustments.get(player.id) is None or adjustments[player.id].tag != "avoid"
        ]
    player_map = {player.id: player for player in adjusted_all}
    levels = replacement_levels(adjusted_all, settings)
    roster = [
        player_map[player_id]
        for player_id in state.rosters.get(settings.user_team_id, ())
        if player_id in player_map
    ]
    current_round = (state.current_pick - 1) // settings.team_count + 1
    caps = position_caps_map(settings)
    cache = MarginalCache(settings, levels, params, caps)

    (
        _adp_from_maps,
        _raw_adjusted,
        _calibrated_from_maps,
        opponent_need_by_id,
        run_pressure,
        schedule,
        intervening_count,
    ) = compute_survival_maps(
        available,
        state,
        settings,
        player_map,
        current_round,
        params,
    )
    from .formula import picks_until_team_turn

    until_next = picks_until_team_turn(state, settings.user_team_id)

    marginals = {player.id: cache.marginal(player, roster) for player in available}
    pool = build_lookahead_pool(available, marginals, params)
    sim_result = simulate_one_turn(
        available,
        marginals,
        pool,
        schedule,
        state,
        settings,
        player_map,
        current_round,
        run_pressure,
        params,
    )
    survival_by_id = sim_result.survival_by_id
    fallback_by_id = sim_result.fallback_by_id
    adp_prior = {
        player.id: adp_prior_survival(
            player, state.current_pick, until_next, intervening_count, params
        )
        for player in available
    }

    wait_by_id = {
        player.id: wait_loss_v4(
            marginals[player.id],
            fallback_by_id[player.id],
            survival_by_id[player.id],
        )
        for player in available
    }

    candidates = select_candidates(available, marginals, wait_by_id, params)
    candidate_ids = {player.id for player in candidates}
    baseline_next = sim_result.expected_best

    next_by_id: dict[str, float] = {}
    for player in available:
        if player.id in candidate_ids:
            next_by_id[player.id] = next_pick_value_from_sim(
                player, roster, pool, cache, sim_result
            )
        else:
            next_by_id[player.id] = baseline_next

    draft_rows: list[_DraftRow] = []
    for player in available:
        player_vorp = vorp(player, levels)
        marginal = marginals[player.id]
        survival = adp_prior[player.id]
        adjusted_survival = survival_by_id[player.id]
        fallback = fallback_by_id[player.id]
        loss = wait_by_id[player.id]
        cliff = tier_cliff(player, available)
        tier_remaining = players_remaining_in_tier(player, available)
        sim_exhaust = sim_result.tier_exhaustion.get((player.position, player.tier), 0.0)
        tier_exhaust = sim_exhaust
        tier_cost = tier_opportunity_cost(
            player,
            available,
            survival_by_id,
            params,
            intervening_picks=intervening_count,
            sim_exhaustion=sim_exhaust,
        )
        next_value = next_by_id[player.id]
        need = roster_shape_need(player.position, roster, settings, current_round)
        shape = shape_adjustment(player.position, roster, settings, current_round, params)
        guardrail = guardrail_adjustment(
            player, player_vorp, roster, settings, current_round
        )
        adjustment = adjustments.get(player.id)
        opinion = adjustment.points_delta if adjustment else 0.0
        tag_bonus = params.my_guy_bonus if adjustment and adjustment.tag == "myGuy" else 0.0

        decision_score = (
            marginal
            + params.wait_loss_weight_v4 * loss
            + params.tier_weight * tier_cost
            + params.lookahead_weight * next_value
            + shape
            + guardrail
            + tag_bonus
        )
        two_pick_path = marginal + next_value
        run = run_pressure.get(player.position, 1.0)

        draft_rows.append(
            _DraftRow(
                player=player,
                player_vorp=player_vorp,
                marginal=marginal,
                survival=survival,
                adjusted_survival=adjusted_survival,
                fallback=fallback,
                loss=loss,
                cliff=cliff,
                tier_remaining=tier_remaining,
                tier_exhaust=tier_exhaust,
                tier_cost=tier_cost,
                next_value=next_value,
                need=need,
                shape=shape,
                guardrail=guardrail,
                adjustment=adjustment,
                opinion=opinion,
                decision_score=decision_score,
                two_pick_path=two_pick_path,
                run=run,
                opponent_need=opponent_need_by_id[player.id],
            )
        )

    best_path = max((row.two_pick_path for row in draft_rows), default=0.0)

    scored: list[RecommendationResult] = []
    for row in draft_rows:
        player = row.player
        reasons = _reasons_v4(
            player,
            row.marginal,
            row.player_vorp,
            row.loss,
            row.survival,
            row.adjusted_survival,
            row.tier_cost,
            row.tier_remaining,
            row.tier_exhaust,
            row.cliff,
            row.next_value,
            row.shape,
            row.guardrail,
            row.adjustment,
            roster,
            settings,
            current_round,
            best_path,
            row.two_pick_path,
        )

        scored.append(
            RecommendationResult(
                player.id,
                player.name,
                player.position,
                round(row.decision_score, 4),
                RecommendationLabel.BEST_PICK,
                RecommendationBreakdown(
                    round(row.player_vorp, 4),
                    round(row.tier_cost, 4),
                    round(row.survival, 4),
                    round(row.need, 4),
                    round(row.opponent_need, 4),
                    round(row.guardrail, 4),
                    round(row.opinion, 4),
                    round(row.marginal, 4),
                    round(row.loss, 4),
                    projected_points=round(player.projected_points, 4),
                    immediate_value=round(row.marginal, 4),
                    adjusted_survival_probability=round(row.adjusted_survival, 4),
                    expected_fallback_value=round(row.fallback, 4),
                    tier_cliff=round(row.cliff, 4),
                    players_remaining_in_tier=row.tier_remaining,
                    tier_exhaustion=round(row.tier_exhaust, 4),
                    tier_opportunity_cost=round(row.tier_cost, 4),
                    opponent_need_factor=round(row.opponent_need, 4),
                    run_pressure=round(row.run, 4),
                    expected_next_pick_value=round(row.next_value, 4),
                    two_pick_path_value=round(row.two_pick_path, 4),
                    shape_adjustment=round(row.shape, 4),
                    decision_score=round(row.decision_score, 4),
                ),
                reasons,
            )
        )

    scored.sort(
        key=lambda result: (
            -result.dvs_score,
            player_map[result.player_id].adp or float("inf"),
            result.player_id,
        )
    )

    labeled: list[RecommendationResult] = []
    top_path = scored[0].breakdown.two_pick_path_value if scored else 0.0
    for index, result in enumerate(scored[:limit]):
        breakdown = result.breakdown
        if (
            breakdown.immediate_value >= params.cant_pass_value_min
            and breakdown.wait_loss >= params.cant_pass_wait_loss_min
            and breakdown.two_pick_path_value >= top_path - 0.5
        ):
            label = RecommendationLabel.CANT_PASS
        elif (
            index > 0
            and breakdown.adjusted_survival_probability >= params.safe_survival_min_v4
            and breakdown.wait_loss <= params.safe_wait_loss_v4
        ):
            label = RecommendationLabel.SAFE_TO_WAIT
        else:
            label = RecommendationLabel.BEST_PICK
        labeled.append(replace(result, tier_label=label))
    return labeled
