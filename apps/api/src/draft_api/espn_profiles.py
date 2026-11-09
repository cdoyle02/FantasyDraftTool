"""Household ESPN cookie profiles for the Week API.

Michael cookies are the default process pair (``ESPN_S2`` / ``ESPN_SWID``).
Katie's pair (``ESPN_S2_KATIE`` / ``ESPN_SWID_KATIE``) is used for Girls Who Ball
unless ``espn_profile`` overrides the league map.
"""

from __future__ import annotations

import os
from typing import Literal

EspnProfileName = Literal["michael", "katie"]

# Girls Who Ball — Katie Doyle's private league (see espn_leagues.json).
KATIE_LEAGUE_IDS: frozenset[str] = frozenset({"1216398267"})


def normalize_swid(swid: str | None) -> str | None:
    """Ensure SWID has surrounding braces when present."""
    if not swid:
        return None
    value = swid.strip()
    if not value:
        return None
    if not value.startswith("{"):
        value = "{" + value.strip("{}") + "}"
    return value


def resolve_espn_profile(
    league_id: str | None = None,
    espn_profile: str | None = None,
) -> EspnProfileName:
    """Pick michael vs katie from explicit override or league id."""
    raw = (espn_profile or "").strip().lower()
    if raw in ("michael", "katie"):
        return raw  # type: ignore[return-value]
    if raw:
        raise ValueError(f"espn_profile must be 'michael' or 'katie', got {espn_profile!r}")
    needle = (league_id or "").strip()
    if needle in KATIE_LEAGUE_IDS:
        return "katie"
    return "michael"


def espn_credentials_for_profile(
    profile: EspnProfileName,
) -> tuple[str | None, str | None, int]:
    """Load cookie pair + season for one profile from the process environment."""
    if profile == "katie":
        espn_s2 = os.getenv("ESPN_S2_KATIE", "").strip() or None
        swid = normalize_swid(os.getenv("ESPN_SWID_KATIE", "").strip() or None)
    else:
        espn_s2 = os.getenv("ESPN_S2", "").strip() or None
        swid = normalize_swid(os.getenv("ESPN_SWID", "").strip() or None)

    season_raw = os.getenv("ESPN_SEASON", "2026").strip() or "2026"
    try:
        season = int(season_raw)
    except ValueError as exc:
        from draft_api.espn_available_dst import EspnAvailableError

        raise EspnAvailableError(f"ESPN_SEASON must be an int, got {season_raw!r}") from exc
    return espn_s2, swid, season
