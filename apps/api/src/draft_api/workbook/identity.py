"""Team identity helpers for the Workbook package.

Re-exports the SoS nflverse team alias map instead of duplicating it: both
packages consume the same nflverse / ESPN team abbreviations, and keeping a
single source of truth avoids the two maps drifting apart. Importing
``draft_api.sos.nflverse`` here is safe because that module has no
dependency (direct or transitive) on ``draft_api.workbook``.
"""

from __future__ import annotations

from draft_api.sos.nflverse import NFL_TEAMS, TEAM_ALIASES

__all__ = ["NFL_TEAMS", "TEAM_ALIASES", "normalize_team"]


def normalize_team(abbrev: str) -> str:
    """Upper-case and alias-map a raw nflverse/ESPN team abbreviation."""
    raw = abbrev.strip().upper()
    return TEAM_ALIASES.get(raw, raw)
