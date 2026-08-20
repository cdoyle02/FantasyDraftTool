"""String-in/string-out entrypoint suitable for Pyodide browser calls."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .formula import recommend
from .models import (
    adjustment_from_dict,
    as_jsonable,
    player_from_dict,
    settings_from_dict,
    state_from_dict,
)


def recommendation_json(payload_json: str) -> str:
    """Calculate recommendations from JSON without Python object bridging."""
    payload: Mapping[str, Any] = json.loads(payload_json)
    settings = settings_from_dict(payload.get("settings", {}))
    state = state_from_dict(
        payload.get("draft_state", payload.get("draftState", {})), settings.team_count
    )
    players = [player_from_dict(item) for item in payload.get("players", ())]
    adjustments = {
        adjustment.player_id: adjustment
        for adjustment in (
            adjustment_from_dict(item) for item in payload.get("adjustments", ())
        )
    }
    results = recommend(players, state, settings, adjustments, int(payload.get("limit", 20)))
    return json.dumps(as_jsonable(results), separators=(",", ":"), sort_keys=True)
