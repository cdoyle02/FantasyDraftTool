"""Public API for the dependency-free DVS engine."""

from .browser import recommendation_json
from .csv_import import CsvImportError, ImportResult, RowIssue, import_players_csv
from .draft import DraftEventError, apply_pick, correct_last_pick, undo_last_pick, validate_state
from .formula import (
    guardrail_adjustment,
    recommend,
    replacement_counts,
    replacement_levels,
    roster_need_multiplier,
    roster_shape_need,
    survival_probability,
    tier_cliff_urgency,
    vorp,
    wait_loss,
)
from .lineup import marginal_value, roster_utility
from .lookahead import wait_loss_v4
from .models import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Pick,
    Player,
    Position,
    RecommendationBreakdown,
    RecommendationLabel,
    RecommendationResult,
    UserAdjustment,
    V5FormulaParams,
    V5RecommendationBreakdown,
    adjustment_from_dict,
    as_jsonable,
    formula_params_from_dict,
    player_from_dict,
    settings_from_dict,
    state_from_dict,
    team_on_clock,
)
from .survival import compute_survival_maps
from .tiers import tier_cliff, tier_opportunity_cost
from .v4 import recommend_v4
from .v5 import recommend_v5

__version__ = "0.1.0"

__all__ = [
    "CsvImportError",
    "DraftEventError",
    "DraftState",
    "FormulaParams",
    "ImportResult",
    "LeagueSettings",
    "Pick",
    "Player",
    "Position",
    "RecommendationBreakdown",
    "RecommendationLabel",
    "RecommendationResult",
    "RowIssue",
    "UserAdjustment",
    "V5FormulaParams",
    "V5RecommendationBreakdown",
    "adjustment_from_dict",
    "apply_pick",
    "as_jsonable",
    "correct_last_pick",
    "compute_survival_maps",
    "formula_params_from_dict",
    "guardrail_adjustment",
    "import_players_csv",
    "marginal_value",
    "player_from_dict",
    "recommend",
    "recommend_v4",
    "recommend_v5",
    "recommendation_json",
    "replacement_counts",
    "replacement_levels",
    "roster_need_multiplier",
    "roster_shape_need",
    "roster_utility",
    "settings_from_dict",
    "state_from_dict",
    "survival_probability",
    "team_on_clock",
    "tier_cliff",
    "tier_cliff_urgency",
    "tier_opportunity_cost",
    "undo_last_pick",
    "validate_state",
    "vorp",
    "wait_loss",
    "wait_loss_v4",
]
