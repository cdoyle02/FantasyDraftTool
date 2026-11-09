"""Team and player identity helpers for the Workbook package.

Re-exports the SoS nflverse team alias map instead of duplicating it: both
packages consume the same nflverse / ESPN team abbreviations, and keeping a
single source of truth avoids the two maps drifting apart. Importing
``draft_api.sos.nflverse`` here is safe because that module has no
dependency (direct or transitive) on ``draft_api.workbook``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from draft_api.sos.nflverse import NFL_TEAMS, TEAM_ALIASES

__all__ = [
    "NFL_TEAMS",
    "PlayerIdIndex",
    "PlayerRef",
    "TEAM_ALIASES",
    "normalize_player_name",
    "normalize_team",
    "player_join_key",
]


def normalize_team(abbrev: str) -> str:
    """Upper-case and alias-map a raw nflverse/ESPN team abbreviation."""
    raw = abbrev.strip().upper()
    return TEAM_ALIASES.get(raw, raw)


def normalize_player_name(name: str) -> str:
    """Lowercase join key: strip accents, punctuation, and suffixes."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\s+(jr|sr|ii|iii|iv)$", "", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True, slots=True)
class PlayerRef:
    """Canonical player identity for Workbook joins (no silent nflverse inventing)."""

    gsis_id: str | None
    espn_player_id: int | None
    display_name: str
    team: str


def player_join_key(display_name: str, team: str) -> str:
    """Stable name+team key for cross-source lookups."""
    return f"{normalize_player_name(display_name)}|{normalize_team(team)}"


@dataclass(frozen=True, slots=True)
class PlayerIdIndex:
    """Exact-id lookup for pool / intel joins (no fuzzy name matching)."""

    by_gsis: dict[str, PlayerRef]
    by_espn: dict[int, PlayerRef]

    @classmethod
    def from_refs(cls, refs: list[PlayerRef]) -> PlayerIdIndex:
        by_gsis: dict[str, PlayerRef] = {}
        by_espn: dict[int, PlayerRef] = {}
        for ref in refs:
            if ref.gsis_id:
                by_gsis[ref.gsis_id] = ref
            if ref.espn_player_id is not None:
                by_espn[int(ref.espn_player_id)] = ref
        return cls(by_gsis=by_gsis, by_espn=by_espn)

    def resolve(
        self,
        *,
        gsis_id: str | None = None,
        espn_player_id: int | None = None,
    ) -> PlayerRef | None:
        if gsis_id and gsis_id in self.by_gsis:
            return self.by_gsis[gsis_id]
        if espn_player_id is not None and espn_player_id in self.by_espn:
            return self.by_espn[espn_player_id]
        return None
