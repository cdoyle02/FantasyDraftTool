"""Typed, serializable domain objects for the DVS engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from typing import Any


class Position(StrEnum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    FLEX = "FLEX"
    SUPERFLEX = "SUPERFLEX"
    K = "K"
    DST = "DST"


class RecommendationLabel(StrEnum):
    CANT_PASS = "CAN'T PASS"
    BEST_PICK = "BEST PICK"
    SAFE_TO_WAIT = "SAFE TO WAIT"


@dataclass(frozen=True, slots=True)
class Player:
    id: str
    name: str
    position: Position
    team: str = ""
    projected_points: float = 0.0
    adp: float | None = None
    tier: int = 1
    depth_chart_rank: int | None = None
    depth_chart_source: str | None = None
    upside_score: float | None = None
    risk_score: float | None = None
    is_rookie: bool = False
    is_breakout: bool = False
    injury_status: str | None = None
    ir_eligible: bool = False
    expected_return_week: int | None = None
    bye_week: int | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("player id and name are required")
        if self.tier < 1:
            raise ValueError("player tier must be at least 1")
        if self.adp is not None and self.adp <= 0:
            raise ValueError("adp must be positive")
        if self.depth_chart_rank is not None and self.depth_chart_rank < 1:
            raise ValueError("depth_chart_rank must be at least 1")
        if self.expected_return_week is not None and self.expected_return_week < 1:
            raise ValueError("expected_return_week must be at least 1")


@dataclass(frozen=True, slots=True)
class UserAdjustment:
    player_id: str
    points_delta: float = 0.0
    tier_override: int | None = None
    tag: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.player_id.strip():
            raise ValueError("player_id is required")
        if not self.player_id.strip():
            raise ValueError("adjustment player_id is required")
        if self.tier_override is not None and self.tier_override < 1:
            raise ValueError("tier override must be at least 1")
        if self.tag not in (None, "myGuy", "avoid", "irStash"):
            raise ValueError("tag must be 'myGuy', 'avoid', 'irStash', or null")


def default_roster_slots() -> dict[str, int]:
    return {
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


def default_flex_weights() -> dict[str, float]:
    return {"RB": 0.45, "WR": 0.45, "TE": 0.10}


def default_superflex_weights() -> dict[str, float]:
    return {"QB": 0.65, "RB": 0.15, "WR": 0.15, "TE": 0.05}


def default_depth_bench_weights() -> dict[str, float]:
    return {"RB": 0.5, "WR": 0.5}


@dataclass(frozen=True, slots=True)
class FormulaParams:
    """Tunable DVS coefficients."""

    formula_version: int = 4
    replacement_index_offset: int = 1
    flex_weights: Mapping[str, float] = field(default_factory=default_flex_weights)
    superflex_weights: Mapping[str, float] = field(default_factory=default_superflex_weights)
    # v1-only composition weights (ignored when formula_version >= 2)
    urgency_weight: float = 1.5
    need_direct_boost: float = 0.22
    need_flex_boost: float = 0.08
    need_bench_penalty_base: float = 0.08
    need_floor: float = 0.55
    # v2/v3 roster utility
    wait_loss_weight: float = 1.0
    bench_discount_default: float = 0.25
    bench_discount_by_depth: tuple[float, ...] = (0.35, 0.25, 0.15)
    # v3 roster-shape need
    need_starter_boost: float = 0.35
    need_flex_boost_v3: float = 0.12
    need_depth_boost: float = 0.08
    need_balance_weight: float = 2.5
    need_duplicate_penalty: float = 0.40
    need_over_target_penalty: float = 0.35
    need_v3_floor: float = 0.35
    need_v3_ceiling: float = 2.0
    need_override_points: float = 30.0
    depth_bench_weights: Mapping[str, float] = field(default_factory=default_depth_bench_weights)
    max_qb: int = 1
    max_te: int = 1
    backup_qb_min_team_count: int = 12
    backup_qb_final_rounds: int = 3
    position_cap_penalty_multiple: float = 6.0
    backup_qb_window_penalty_multiple: float = 0.5
    # shared survival / demand
    survival_default_no_adp: float = 0.5
    survival_spread_min: float = 4.0
    survival_spread_adp_factor: float = 0.16
    survival_clamp_low: float = 0.01
    survival_clamp_high: float = 0.99
    opponent_demand_weight: float = 0.15
    # preferences and guardrail labels
    my_guy_bonus: float = 6.0
    exclude_avoid_tag: bool = True
    # v1 labels
    cant_pass_vorp_min: float = 20.0
    cant_pass_survival_max: float = 0.30
    safe_to_wait_survival_min: float = 0.65
    # v2/v3 labels
    value_min: float = 5.0
    urgent_wait_loss: float = 8.0
    safe_wait_loss: float = 3.0
    # v4 decision engine
    lookahead_weight: float = 0.85
    lookahead_candidates: int = 12
    lookahead_pool_per_position: int = 6
    wait_loss_weight_v4: float = 0.35
    tier_weight: float = 0.30
    tier_cliff_scale: float = 25.0
    opponent_demand_weight_v4: float = 0.6
    opponent_demand_min: float = 0.5
    opponent_demand_max: float = 2.0
    survival_calibrate: bool = True
    run_weight: float = 0.6
    run_prior_strength: float = 8.0
    run_window_picks: int = 12
    need_points_scale: float = 12.0
    need_points_cap: float = 18.0
    # v4 labels
    cant_pass_value_min: float = 5.0
    cant_pass_wait_loss_min: float = 6.0
    safe_wait_loss_v4: float = 2.5
    safe_survival_min_v4: float = 0.70
    one_turn_sims: int = 48
    sim_seed: int = 2026
    sim_pick_pool: int = 40
    # v4.1 special teams (K/DST)
    special_teams_hard_gate: bool = True
    kicker_final_rounds: int = 1
    dst_final_rounds: int = 2
    special_teams_timing_penalty_multiple: float = 3.0
    special_teams_tier_scale: float = 0.0
    special_teams_wait_loss_scale: float = 0.0
    special_teams_run_pressure: bool = False
    special_teams_lookahead_mode: str = "eligibility_window"
    # v4.1 late-round phase transition
    late_phase_start_progress: float = 0.55
    upside_weight_max: float = 6.0
    upside_starter_damp: float = 0.25
    upside_reference_score: float = 5.0
    upside_score_span: float = 5.0
    rookie_upside_bonus: float = 0.15
    breakout_upside_bonus: float = 0.15
    # v4.1 contingent / handcuff
    handcuff_positions: tuple[str, ...] = ("RB",)
    handcuff_max_depth_rank: int = 2
    handcuff_base_role_probability: float = 0.30
    handcuff_risk_sensitivity: float = 0.20
    handcuff_risk_modifier_min: float = 0.85
    handcuff_risk_modifier_max: float = 1.20
    handcuff_derived_depth_confidence: float = 0.70
    handcuff_inherit_share: float = 0.60
    handcuff_min_starter_surplus: float = 20.0
    handcuff_min_reason_points: float = 1.0
    handcuff_weight_max: float = 5.0
    handcuff_max_bonus: float = 6.0
    # v4.1 IR stash
    ir_stash_final_rounds: int = 3
    ir_stash_weight: float = 4.0
    ir_stash_max_bonus: float = 8.0
    ir_return_week_horizon: int = 8
    # v4.1 combination / replacement
    optionality_combine: str = "max"
    demand_adjusted_replacement: bool = False

    def __post_init__(self) -> None:
        if self.formula_version not in (1, 2, 3, 4):
            raise ValueError("formula_version must be 1, 2, 3, or 4")
        if self.special_teams_lookahead_mode not in (
            "never",
            "eligibility_window",
            "always",
        ):
            raise ValueError("special_teams_lookahead_mode is invalid")
        if self.optionality_combine not in ("max", "sum"):
            raise ValueError("optionality_combine must be 'max' or 'sum'")


@dataclass(frozen=True, slots=True)
class V5FormulaParams(FormulaParams):
    """Formula V5 coefficients extending V4 defaults."""

    formula_version: int = 5
    v5_policy_strength: float = 1.0
    negative_vorp_bench_weight: float = 4.0
    negative_vorp_bench_cap: float = 3.0
    negative_vorp_starter_damp: float = 0.15
    own_handcuff_factor_8_team: float = 0.45
    own_handcuff_factor_10_team: float = 0.725
    own_handcuff_factor_12_team: float = 1.0
    own_handcuff_factor_14_team: float = 1.10
    own_handcuff_second_multiplier: float = 0.40
    own_handcuff_third_multiplier: float = 0.20
    own_handcuff_fourth_plus_multiplier: float = 0.05
    bench_balance_band_half_width: float = 0.10
    bench_balance_usable_vorp_floor_ratio: float = -0.25
    bench_balance_reserve_slots: float = 2.0
    bench_balance_max_adjustment: float = 3.0
    reliability_weight_max: float = 0.75
    reliability_close_score_threshold: float = 1.25
    reliability_target_risk: float = 5.0
    reliability_risk_span: float = 2.5
    reliability_min_known_players: int = 2
    reliability_flex_weight: float = 0.75
    reliability_reserve_weight: float = 0.35
    reliability_reserve_slots: int = 1

    def __post_init__(self) -> None:
        if self.formula_version != 5:
            raise ValueError("V5FormulaParams requires formula_version=5")
        if not 0.0 <= self.v5_policy_strength <= 1.0:
            raise ValueError("v5_policy_strength must be between 0 and 1")
        if self.special_teams_lookahead_mode not in (
            "never",
            "eligibility_window",
            "always",
        ):
            raise ValueError("special_teams_lookahead_mode is invalid")
        if self.optionality_combine not in ("max", "sum"):
            raise ValueError("optionality_combine must be 'max' or 'sum'")


@dataclass(frozen=True, slots=True)
class LeagueSettings:
    team_count: int = 12
    roster_slots: Mapping[str, int] = field(default_factory=default_roster_slots)
    scoring_format: str = "PPR"
    draft_type: str = "snake"
    league_type: str = "redraft"
    user_team_id: str = "1"
    qb_te_vorp_threshold: float = 45.0
    guardrail_weight: float = 12.0
    formula_params: FormulaParams = field(default_factory=FormulaParams)
    keeper_slots: int = 0
    ir_slots: int = 0

    def __post_init__(self) -> None:
        if not 2 <= self.team_count <= 32:
            raise ValueError("team_count must be between 2 and 32")
        if any(int(value) < 0 for value in self.roster_slots.values()):
            raise ValueError("roster slot counts cannot be negative")
        if self.scoring_format not in ("PPR", "halfPPR", "standard"):
            raise ValueError("unsupported scoring format")
        if self.draft_type != "snake":
            raise ValueError("only snake drafts are supported")
        if self.keeper_slots < 0:
            raise ValueError("keeper_slots cannot be negative")
        if self.ir_slots < 0:
            raise ValueError("ir_slots cannot be negative")

    @property
    def roster_size(self) -> int:
        return sum(int(value) for value in self.roster_slots.values())

    @property
    def rounds(self) -> int:
        return max(1, self.roster_size - self.keeper_slots)


@dataclass(frozen=True, slots=True)
class Pick:
    pick_number: int
    team_id: str
    player_id: str
    timestamp: str = ""
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.pick_number < 1:
            raise ValueError("pick_number must be positive")
        if not self.team_id or not self.player_id:
            raise ValueError("team_id and player_id are required")
        if not self.event_id:
            object.__setattr__(
                self, "event_id", f"pick-{self.pick_number}-{self.team_id}-{self.player_id}"
            )


@dataclass(frozen=True, slots=True)
class DraftState:
    team_count: int
    pick_history: tuple[Pick, ...] = ()
    reserved_rosters: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def current_pick(self) -> int:
        return len(self.pick_history) + 1

    @property
    def team_on_clock(self) -> str:
        return team_on_clock(self.current_pick, self.team_count)

    @property
    def rosters(self) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {str(index): [] for index in range(1, self.team_count + 1)}
        for team_id, player_ids in self.reserved_rosters.items():
            result.setdefault(team_id, []).extend(player_ids)
        for pick in self.pick_history:
            result.setdefault(pick.team_id, []).append(pick.player_id)
        return {team: tuple(players) for team, players in result.items()}

    @property
    def drafted_ids(self) -> frozenset[str]:
        reserved = {
            player_id
            for player_ids in self.reserved_rosters.values()
            for player_id in player_ids
        }
        picked = {pick.player_id for pick in self.pick_history}
        return frozenset(reserved | picked)


@dataclass(frozen=True, slots=True)
class RecommendationBreakdown:
    vorp: float
    tier_urgency: float
    survival_probability: float
    need_multiplier: float
    opponent_demand_factor: float
    guardrail_adjustment: float
    user_adjustment: float
    marginal_value: float = 0.0
    wait_loss: float = 0.0
    projected_points: float = 0.0
    immediate_value: float = 0.0
    adjusted_survival_probability: float = 0.0
    expected_fallback_value: float = 0.0
    tier_cliff: float = 0.0
    players_remaining_in_tier: int = 0
    tier_exhaustion: float = 0.0
    tier_opportunity_cost: float = 0.0
    opponent_need_factor: float = 1.0
    run_pressure: float = 1.0
    expected_next_pick_value: float = 0.0
    two_pick_path_value: float = 0.0
    shape_adjustment: float = 0.0
    decision_score: float = 0.0
    late_round_upside: float = 0.0
    contingent_value: float = 0.0
    handcuff_bonus: float = 0.0
    ir_stash_value: float = 0.0
    optionality_value: float = 0.0
    special_teams_timing_penalty: float = 0.0
    special_teams_position_cap: bool = False
    late_phase_weight: float = 0.0
    starter_completion: float = 0.0
    starter_slots_filled: int = 0
    starter_slots_total: int = 0
    replacement_level: float = 0.0
    replacement_demand: float = 0.0


@dataclass(frozen=True, slots=True)
class V5RecommendationBreakdown(RecommendationBreakdown):
    negative_vorp_adjustment: float = 0.0
    raw_handcuff_bonus: float = 0.0
    adjusted_handcuff_bonus: float = 0.0
    own_handcuff_league_multiplier: float = 1.0
    own_handcuff_count: int = 0
    own_handcuff_count_multiplier: float = 1.0
    bench_balance_adjustment: float = 0.0
    usable_rb_depth: float = 0.0
    usable_wr_depth: float = 0.0
    roster_risk_score: float = 0.0
    pre_reliability_score: float = 0.0
    reliability_adjustment: float = 0.0
    v5_policy_strength: float = 1.0


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    player_id: str
    player_name: str
    position: Position
    dvs_score: float
    tier_label: RecommendationLabel
    breakdown: RecommendationBreakdown
    reasons: tuple[str, ...] = ()


def team_on_clock(pick_number: int, team_count: int) -> str:
    if pick_number < 1 or team_count < 2:
        raise ValueError("invalid pick number or team count")
    round_index, offset = divmod(pick_number - 1, team_count)
    seat = offset + 1 if round_index % 2 == 0 else team_count - offset
    return str(seat)


def as_jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return as_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): as_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [as_jsonable(item) for item in value]
    return value


def player_from_dict(data: Mapping[str, Any]) -> Player:
    return Player(
        id=str(data["id"]),
        name=str(data["name"]),
        position=Position(str(data["position"]).upper()),
        team=str(data.get("team", "")),
        projected_points=float(data.get("projected_points", data.get("projectedPoints", 0))),
        adp=_optional_float(data.get("adp")),
        tier=int(data.get("tier", 1)),
        depth_chart_rank=_optional_int(
            data.get("depth_chart_rank", data.get("depthChartRank"))
        ),
        depth_chart_source=_optional_str(
            data.get("depth_chart_source", data.get("depthChartSource"))
        ),
        upside_score=_optional_float(data.get("upside_score", data.get("upsideScore"))),
        risk_score=_optional_float(data.get("risk_score", data.get("riskScore"))),
        is_rookie=bool(data.get("is_rookie", data.get("isRookie", False))),
        is_breakout=bool(data.get("is_breakout", data.get("isBreakout", False))),
        injury_status=_optional_str(data.get("injury_status", data.get("injuryStatus"))),
        ir_eligible=bool(data.get("ir_eligible", data.get("irEligible", False))),
        expected_return_week=_optional_int(
            data.get("expected_return_week", data.get("expectedReturnWeek"))
        ),
        bye_week=_optional_int(data.get("bye_week", data.get("byeWeek"))),
    )


def adjustment_from_dict(data: Mapping[str, Any]) -> UserAdjustment:
    player_id = data.get("player_id", data.get("playerId"))
    if player_id is None:
        raise ValueError("adjustment player_id is required")
    return UserAdjustment(
        player_id=str(player_id),
        points_delta=float(data.get("points_delta", data.get("pointsDelta", 0))),
        tier_override=_optional_int(data.get("tier_override", data.get("tierOverride"))),
        tag=data.get("tag"),
        note=str(data.get("note", "")),
    )


def formula_params_from_dict(data: Mapping[str, Any] | None) -> FormulaParams:
    if not data:
        return FormulaParams()
    payload = dict(data)
    if "formulaVersion" in payload and "formula_version" not in payload:
        payload["formula_version"] = payload.pop("formulaVersion")
    version = int(payload.get("formula_version", 4))
    if version == 5:
        allowed = {item.name for item in fields(V5FormulaParams)}
        filtered = {key: value for key, value in payload.items() if key in allowed}
        return V5FormulaParams(**filtered)
    allowed = {item.name for item in fields(FormulaParams)}
    filtered = {key: value for key, value in payload.items() if key in allowed}
    return FormulaParams(**filtered)


def settings_from_dict(data: Mapping[str, Any]) -> LeagueSettings:
    formula_payload = data.get("formula_params", data.get("formulaParams"))
    formula_version = data.get("formula_version", data.get("formulaVersion"))
    if formula_version is not None and formula_payload is None:
        formula_payload = {"formula_version": formula_version}
    elif formula_version is not None and formula_payload is not None:
        formula_payload = dict(formula_payload)
        formula_payload.setdefault("formula_version", formula_version)
    return LeagueSettings(
        team_count=int(data.get("team_count", data.get("teamCount", 12))),
        roster_slots=dict(
            data.get("roster_slots", data.get("rosterSlots", default_roster_slots()))
        ),
        scoring_format=str(data.get("scoring_format", data.get("scoringFormat", "PPR"))),
        draft_type=str(data.get("draft_type", data.get("draftType", "snake"))),
        league_type=str(data.get("league_type", data.get("leagueType", "redraft"))),
        user_team_id=str(data.get("user_team_id", data.get("userTeamId", "1"))),
        qb_te_vorp_threshold=float(
            data.get("qb_te_vorp_threshold", data.get("qbTeVorpThreshold", 45))
        ),
        guardrail_weight=float(data.get("guardrail_weight", data.get("guardrailWeight", 12))),
        formula_params=formula_params_from_dict(formula_payload),
        keeper_slots=int(data.get("keeper_slots", data.get("keeperSlots", 0))),
        ir_slots=int(data.get("ir_slots", data.get("irSlots", 0))),
    )


def state_from_dict(data: Mapping[str, Any], team_count: int | None = None) -> DraftState:
    picks: Sequence[Mapping[str, Any]] = data.get("pick_history", data.get("pickHistory", ()))
    reserved_raw = data.get("reserved_rosters", data.get("reservedRosters", {}))
    reserved_rosters = {
        str(team_id): tuple(str(player_id) for player_id in player_ids)
        for team_id, player_ids in reserved_raw.items()
    }
    return DraftState(
        team_count=int(data.get("team_count", data.get("teamCount", team_count or 12))),
        pick_history=tuple(
            Pick(
                pick_number=int(item.get("pick_number", item.get("pickNumber"))),
                team_id=str(item.get("team_id", item.get("teamId"))),
                player_id=str(item.get("player_id", item.get("playerId"))),
                timestamp=str(item.get("timestamp", "")),
                event_id=str(item.get("event_id", item.get("eventId", item.get("id", "")))),
            )
            for item in picks
        ),
        reserved_rosters=reserved_rosters,
    )


def _optional_float(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
