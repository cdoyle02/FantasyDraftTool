"""Typed, serializable domain objects for the DVS engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
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

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("player id and name are required")
        if self.tier < 1:
            raise ValueError("player tier must be at least 1")
        if self.adp is not None and self.adp <= 0:
            raise ValueError("adp must be positive")


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
        if self.tag not in (None, "myGuy", "avoid"):
            raise ValueError("tag must be 'myGuy', 'avoid', or null")


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


@dataclass(frozen=True, slots=True)
class FormulaParams:
    """Tunable DVS coefficients."""

    formula_version: int = 2
    replacement_index_offset: int = 1
    flex_weights: Mapping[str, float] = field(default_factory=default_flex_weights)
    superflex_weights: Mapping[str, float] = field(default_factory=default_superflex_weights)
    # v1-only composition weights (ignored when formula_version >= 2)
    urgency_weight: float = 1.5
    need_direct_boost: float = 0.22
    need_flex_boost: float = 0.08
    need_bench_penalty_base: float = 0.08
    need_floor: float = 0.55
    # v2 roster utility
    wait_loss_weight: float = 1.0
    bench_discount_default: float = 0.25
    bench_discount_by_depth: tuple[float, ...] = (0.35, 0.25, 0.15)
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
    # v2 labels
    value_min: float = 5.0
    urgent_wait_loss: float = 8.0
    safe_wait_loss: float = 3.0

    def __post_init__(self) -> None:
        if self.formula_version not in (1, 2):
            raise ValueError("formula_version must be 1 or 2")


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

    def __post_init__(self) -> None:
        if not 2 <= self.team_count <= 32:
            raise ValueError("team_count must be between 2 and 32")
        if any(int(value) < 0 for value in self.roster_slots.values()):
            raise ValueError("roster slot counts cannot be negative")
        if self.scoring_format not in ("PPR", "halfPPR", "standard"):
            raise ValueError("unsupported scoring format")
        if self.draft_type != "snake":
            raise ValueError("only snake drafts are supported")

    @property
    def rounds(self) -> int:
        return sum(int(value) for value in self.roster_slots.values())


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

    @property
    def current_pick(self) -> int:
        return len(self.pick_history) + 1

    @property
    def team_on_clock(self) -> str:
        return team_on_clock(self.current_pick, self.team_count)

    @property
    def rosters(self) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {str(index): [] for index in range(1, self.team_count + 1)}
        for pick in self.pick_history:
            result.setdefault(pick.team_id, []).append(pick.player_id)
        return {team: tuple(players) for team, players in result.items()}


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


def settings_from_dict(data: Mapping[str, Any]) -> LeagueSettings:
    return LeagueSettings(
        team_count=int(data.get("team_count", data.get("teamCount", 12))),
        roster_slots=dict(
            data.get("roster_slots", data.get("rosterSlots", default_roster_slots()))
        ),
        scoring_format=str(data.get("scoring_format", data.get("scoringFormat", "PPR"))),
        draft_type=str(data.get("draft_type", data.get("draftType", "snake"))),
        league_type=str(data.get("league_type", data.get("leagueType", "redraft"))),
        user_team_id=str(data.get("user_team_id", data.get("userTeamId", "1"))),
        qb_te_vorp_threshold=float(data.get("qb_te_vorp_threshold", 45)),
        guardrail_weight=float(data.get("guardrail_weight", 12)),
    )


def state_from_dict(data: Mapping[str, Any], team_count: int | None = None) -> DraftState:
    picks: Sequence[Mapping[str, Any]] = data.get("pick_history", data.get("pickHistory", ()))
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
    )


def _optional_float(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)
