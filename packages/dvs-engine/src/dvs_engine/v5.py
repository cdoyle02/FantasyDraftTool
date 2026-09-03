"""V5 draft decision engine: targeted late-round roster construction evolution."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .formula import (
    effective_player,
    picks_until_team_turn,
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
from dataclasses import fields

from .models import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    RecommendationLabel,
    RecommendationResult,
    UserAdjustment,
    V5FormulaParams,
    V5RecommendationBreakdown,
)
from .phase import draft_phase
from .simulate import adp_prior_survival, next_pick_value_from_sim, simulate_one_turn
from .special_teams import is_special_teams_eligible, special_teams_status
from .survival import compute_survival_maps
from .tiers import (
    players_remaining_in_tier,
    tier_cliff,
    tier_opportunity_cost,
)
from .v4 import _reasons_v4
from .v5_optionality import optionality_for_player_v5
from .v5_policy import (
    apply_reliability_buckets,
    bench_balance_adjustment,
    compose_guardrail_for_v5,
    compose_shape_for_v5,
    negative_vorp_adjustment,
    raw_reliability_fit,
    roster_risk_score,
)


def _v5_params(settings: LeagueSettings) -> V5FormulaParams:
    params = settings.formula_params
    if isinstance(params, V5FormulaParams):
        return params
    base = {field.name: getattr(params, field.name) for field in fields(FormulaParams)}
    return V5FormulaParams(**base)


def _reasons_v5(
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
    optionality: float,
    optionality_reason: str | None,
    phase_late_weight: float,
    neg_vorp_adj: float,
    bench_adj: float,
    reliability_adj: float,
    own_handcuff_reason: str | None,
) -> tuple[str, ...]:
    reasons = list(
        _reasons_v4(
            player,
            marginal,
            player_vorp,
            wait_loss,
            survival,
            adjusted_survival,
            tier_cost,
            tier_remaining,
            tier_exhaust,
            cliff,
            next_value,
            shape,
            guardrail,
            adjustment,
            roster,
            settings,
            current_round,
            best_path,
            player_path,
            optionality,
            optionality_reason,
            phase_late_weight,
        )
    )
    if neg_vorp_adj <= -1.0:
        reasons.append("significantly below shallow-league replacement level")
    if own_handcuff_reason and own_handcuff_reason not in reasons:
        reasons.append(own_handcuff_reason)
    if abs(bench_adj) >= 1.0:
        if bench_adj > 0:
            reasons.append("roster already has sufficient RB/WR depth")
        else:
            reasons.append("meaningful RB/WR bench imbalance")
    if reliability_adj >= 0.25:
        reasons.append("adds reliability to a volatile WR/FLEX group")
    elif reliability_adj <= -0.25:
        reasons.append("increases portfolio volatility")
    return tuple(reasons)


@dataclass(frozen=True, slots=True)
class _V5DraftRow:
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
    tag_bonus: float
    two_pick_path: float
    run: float
    opponent_need: float
    optionality: float
    optionality_reason: str | None
    late_round_upside: float
    contingent_value: float
    handcuff_bonus: float
    ir_stash_value: float
    raw_handcuff_bonus: float
    adjusted_handcuff_bonus: float
    own_handcuff_league_multiplier: float
    own_handcuff_count: int
    own_handcuff_count_multiplier: float
    special_teams_timing_penalty: float
    special_teams_position_cap: bool
    phase_late_weight: float
    starter_completion: float
    starter_slots_filled: int
    starter_slots_total: int
    negative_vorp_adjustment: float
    bench_balance_adjustment: float
    usable_rb_depth: float
    usable_wr_depth: float
    roster_risk_score: float
    pre_reliability_score: float
    reliability_adjustment: float = 0.0
    decision_score: float = 0.0


def recommend_v5(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    adjustments: Mapping[str, UserAdjustment] | None = None,
    limit: int = 20,
) -> list[RecommendationResult]:
    params = _v5_params(settings)
    settings = replace(settings, formula_params=params)
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
    available = [
        player
        for player in available
        if is_special_teams_eligible(player, roster, settings, current_round, params)
    ]
    caps = position_caps_map(settings)
    cache = MarginalCache(settings, levels, params, caps)
    phase = draft_phase(roster, settings, levels, params, current_round, caps)
    portfolio_risk = roster_risk_score(roster, settings, levels, params)

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

    until_next = picks_until_team_turn(state, settings.user_team_id)
    next_round = (state.current_pick + until_next - 1) // settings.team_count + 1

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

    candidates = select_candidates(
        available,
        marginals,
        wait_by_id,
        params,
        roster=roster,
        settings=settings,
        current_round=current_round,
    )
    candidate_ids = {player.id for player in candidates}
    baseline_next = sim_result.expected_best

    next_by_id: dict[str, float] = {}
    for player in available:
        if player.id in candidate_ids:
            next_by_id[player.id] = next_pick_value_from_sim(
                player,
                roster,
                pool,
                cache,
                sim_result,
                settings,
                next_round,
                params,
            )
        else:
            next_by_id[player.id] = baseline_next

    draft_rows: list[_V5DraftRow] = []
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
        if player.position in (Position.K, Position.DST):
            tier_cost *= params.special_teams_tier_scale
            loss *= params.special_teams_wait_loss_scale
        next_value = next_by_id[player.id]
        need = roster_shape_need(player.position, roster, settings, current_round)
        shape = compose_shape_for_v5(
            player.position, roster, settings, current_round, params, phase.late_weight
        )
        guardrail = compose_guardrail_for_v5(
            player, player_vorp, roster, settings, current_round, params, phase.late_weight
        )
        st_status = special_teams_status(
            player, roster, settings, current_round, params
        )
        opt = optionality_for_player_v5(
            player,
            roster,
            settings,
            levels,
            phase,
            params,
            current_round,
        )
        neg_adj = negative_vorp_adjustment(
            player,
            player_vorp,
            levels.get(player.position, 0.0),
            phase,
            params,
        )
        bench_adj, usable_rb, usable_wr = bench_balance_adjustment(
            player, roster, settings, levels, phase, params
        )
        adjustment = adjustments.get(player.id)
        opinion = adjustment.points_delta if adjustment else 0.0
        tag_bonus = params.my_guy_bonus if adjustment and adjustment.tag == "myGuy" else 0.0

        pre_reliability = (
            marginal
            + params.wait_loss_weight_v4 * loss
            + params.tier_weight * tier_cost
            + params.lookahead_weight * next_value
            + shape
            + guardrail
            + tag_bonus
            + opt.optionality_value
            + neg_adj
            + bench_adj
        )
        two_pick_path = marginal + next_value
        run = run_pressure.get(player.position, 1.0)

        draft_rows.append(
            _V5DraftRow(
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
                tag_bonus=tag_bonus,
                two_pick_path=two_pick_path,
                run=run,
                opponent_need=opponent_need_by_id[player.id],
                optionality=opt.optionality_value,
                optionality_reason=opt.reason,
                late_round_upside=opt.late_round_upside,
                contingent_value=opt.contingent_value,
                handcuff_bonus=opt.handcuff_bonus,
                ir_stash_value=opt.ir_stash_value,
                raw_handcuff_bonus=opt.raw_handcuff_bonus,
                adjusted_handcuff_bonus=opt.adjusted_handcuff_bonus,
                own_handcuff_league_multiplier=opt.own_handcuff_league_multiplier,
                own_handcuff_count=opt.own_handcuff_count,
                own_handcuff_count_multiplier=opt.own_handcuff_count_multiplier,
                special_teams_timing_penalty=st_status.timing_penalty,
                special_teams_position_cap=st_status.cap_blocked,
                phase_late_weight=phase.late_weight,
                starter_completion=phase.starter_completion,
                starter_slots_filled=phase.starter_slots_filled,
                starter_slots_total=phase.starter_slots_total,
                negative_vorp_adjustment=neg_adj,
                bench_balance_adjustment=bench_adj,
                usable_rb_depth=usable_rb,
                usable_wr_depth=usable_wr,
                roster_risk_score=portfolio_risk,
                pre_reliability_score=pre_reliability,
            )
        )

    reliability_fits = {
        row.player.id: raw_reliability_fit(row.player, portfolio_risk, phase, params)
        for row in draft_rows
    }
    pre_scores = {row.player.id: row.pre_reliability_score for row in draft_rows}
    reliability_by_id = apply_reliability_buckets(pre_scores, reliability_fits, params)

    for index, row in enumerate(draft_rows):
        rel = reliability_by_id.get(row.player.id, 0.0)
        decision = row.pre_reliability_score + rel
        draft_rows[index] = replace(
            row,
            reliability_adjustment=rel,
            decision_score=decision,
        )

    best_path = max((row.two_pick_path for row in draft_rows), default=0.0)

    scored: list[RecommendationResult] = []
    for row in draft_rows:
        player = row.player
        own_reason = None
        if params.v5_policy_strength > 0.0 and row.raw_handcuff_bonus >= params.handcuff_min_reason_points and (
            row.own_handcuff_league_multiplier < 0.99 or row.own_handcuff_count >= 1
        ):
            own_reason = row.optionality_reason

        reasons = _reasons_v5(
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
            row.optionality,
            row.optionality_reason,
            row.phase_late_weight,
            row.negative_vorp_adjustment,
            row.bench_balance_adjustment,
            row.reliability_adjustment,
            own_reason,
        )

        scored.append(
            RecommendationResult(
                player.id,
                player.name,
                player.position,
                round(row.decision_score, 4),
                RecommendationLabel.BEST_PICK,
                V5RecommendationBreakdown(
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
                    late_round_upside=round(row.late_round_upside, 4),
                    contingent_value=round(row.contingent_value, 4),
                    handcuff_bonus=round(row.handcuff_bonus, 4),
                    ir_stash_value=round(row.ir_stash_value, 4),
                    optionality_value=round(row.optionality, 4),
                    special_teams_timing_penalty=round(row.special_teams_timing_penalty, 4),
                    special_teams_position_cap=row.special_teams_position_cap,
                    late_phase_weight=round(row.phase_late_weight, 4),
                    starter_completion=round(row.starter_completion, 4),
                    starter_slots_filled=row.starter_slots_filled,
                    starter_slots_total=row.starter_slots_total,
                    replacement_level=round(levels.get(player.position, 0.0), 4),
                    negative_vorp_adjustment=round(row.negative_vorp_adjustment, 4),
                    raw_handcuff_bonus=round(row.raw_handcuff_bonus, 4),
                    adjusted_handcuff_bonus=round(row.adjusted_handcuff_bonus, 4),
                    own_handcuff_league_multiplier=round(row.own_handcuff_league_multiplier, 4),
                    own_handcuff_count=row.own_handcuff_count,
                    own_handcuff_count_multiplier=round(row.own_handcuff_count_multiplier, 4),
                    bench_balance_adjustment=round(row.bench_balance_adjustment, 4),
                    usable_rb_depth=round(row.usable_rb_depth, 4),
                    usable_wr_depth=round(row.usable_wr_depth, 4),
                    roster_risk_score=round(row.roster_risk_score, 4),
                    pre_reliability_score=round(row.pre_reliability_score, 4),
                    reliability_adjustment=round(row.reliability_adjustment, 4),
                    v5_policy_strength=round(params.v5_policy_strength, 4),
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
