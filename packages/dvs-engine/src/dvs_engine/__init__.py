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
    adjustment_from_dict,
    as_jsonable,
    player_from_dict,
    settings_from_dict,
    state_from_dict,
    team_on_clock,
)

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
    "adjustment_from_dict",
    "apply_pick",
    "as_jsonable",
    "correct_last_pick",
    "guardrail_adjustment",
    "import_players_csv",
    "marginal_value",
    "player_from_dict",
    "recommend",
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
    "tier_cliff_urgency",
    "undo_last_pick",
    "validate_state",
    "vorp",
    "wait_loss",
]
