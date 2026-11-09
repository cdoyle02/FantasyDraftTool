"""Rank a pasted DFS player pool against Workbook Net matchup metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from draft_api.workbook.fantasy import Scoring
from draft_api.workbook.identity import (
  PlayerIdIndex,
  normalize_player_name,
  normalize_team,
)
from draft_api.workbook.matrices import Tertile, assign_tertile
from draft_api.workbook.nflverse import WorkbookDataset

JoinStatus = Literal["matched", "unmatched"]
MAX_POOL_PLAYERS = 500

_POSITION_TO_GROUP: dict[str, str] = {
  "QB": "qb",
  "RB": "rb",
  "WR": "wr",
  "TE": "te",
}
_HEADLINE_KEY: dict[str, str] = {"qb": "fpGTot", "rb": "fpGTot", "wr": "fpG", "te": "fpG"}


@dataclass(frozen=True, slots=True)
class PoolPlayerInput:
  name: str
  team: str
  salary: int
  position: str
  opponent: str | None = None
  gsis_id: str | None = None
  espn_player_id: int | None = None


@dataclass(frozen=True, slots=True)
class PoolRankRow:
  name: str
  team: str
  salary: int
  position: str
  matchup_team: str | None
  opponent: str | None
  net_fp_g: float | None
  tier: Tertile | None
  join_status: JoinStatus
  value: float | None


def _matchup_net_fp(
  dataset: WorkbookDataset,
  *,
  team: str,
  opponent: str,
  group: str,
  weeks: set[int],
  scoring: Scoring,
) -> float | None:
  from draft_api.workbook.service import _positional_block  # local: same pattern as matrices

  block = _positional_block(
    dataset,
    group={"qb": "qb", "rb": "rb", "wr": "all_wr", "te": "te"}[group],
    team=team,
    opponent=opponent,
    weeks=weeks,
    scoring=scoring,
  )
  headline = _HEADLINE_KEY.get(group, "fpG")
  value = block.get(headline)
  if isinstance(value, (int, float)):
    return float(value)
  return None


def rank_pool(
  players: list[PoolPlayerInput],
  *,
  dataset: WorkbookDataset,
  week: int,
  weeks: set[int],
  scoring: Scoring,
  id_index: PlayerIdIndex | None = None,
) -> list[PoolRankRow]:
  """Rank pasted pool players by salary-adjusted Net FP/G for their matchup.

  Join order (still no fuzzy names): optional ``gsis_id`` / ``espn_player_id``
  via ``id_index``, then exact team membership + schedule for the board week.
  """
  if len(players) > MAX_POOL_PLAYERS:
    raise ValueError(f"pool exceeds {MAX_POOL_PLAYERS} players")

  draft_rows: list[PoolRankRow] = []
  for player in players:
    resolved = (
      id_index.resolve(gsis_id=player.gsis_id, espn_player_id=player.espn_player_id)
      if id_index is not None
      else None
    )
    team = normalize_team(resolved.team if resolved is not None else player.team)
    position = player.position.strip().upper()
    group = _POSITION_TO_GROUP.get(position)
    opponent = (dataset.schedule.get(week) or {}).get(team)
    matched = (
      group is not None
      and team in dataset.teams
      and opponent is not None
      and normalize_player_name(player.name) != ""
    )
    net_fp_g: float | None = None
    if matched and opponent:
      net_fp_g = _matchup_net_fp(
        dataset,
        team=team,
        opponent=opponent,
        group=group,
        weeks=weeks,
        scoring=scoring,
      )

    draft_rows.append(
      PoolRankRow(
        name=player.name,
        team=team,
        salary=player.salary,
        position=position,
        matchup_team=team if matched else None,
        opponent=opponent if matched else player.opponent,
        net_fp_g=net_fp_g,
        tier=None,
        join_status="matched" if matched else "unmatched",
        value=None,
      )
    )

  net_values = {
    f"{row.name}|{row.team}": row.net_fp_g
    for row in draft_rows
    if row.net_fp_g is not None
  }
  tiers = assign_tertile(net_values, higher_is_better=True)

  enriched: list[PoolRankRow] = []
  for row in draft_rows:
    key = f"{row.name}|{row.team}"
    tier = tiers.get(key)
    value: float | None = None
    if row.net_fp_g is not None and row.salary > 0:
      value = round(row.net_fp_g / row.salary * 1000.0, 4)
    enriched.append(
      PoolRankRow(
        name=row.name,
        team=row.team,
        salary=row.salary,
        position=row.position,
        matchup_team=row.matchup_team,
        opponent=row.opponent,
        net_fp_g=round(row.net_fp_g, 2) if row.net_fp_g is not None else None,
        tier=tier,
        join_status=row.join_status,
        value=value,
      )
    )

  enriched.sort(
    key=lambda row: (
      row.value is None,
      -(row.value or 0.0),
      row.net_fp_g is None,
      -(row.net_fp_g or 0.0),
      row.name.lower(),
    )
  )
  return enriched


def row_to_json(row: PoolRankRow) -> dict[str, object]:
  return {
    "name": row.name,
    "team": row.team,
    "salary": row.salary,
    "position": row.position,
    "matchupTeam": row.matchup_team,
    "opponent": row.opponent,
    "netFpG": row.net_fp_g,
    "tier": row.tier,
    "joinStatus": row.join_status,
    "value": row.value,
  }
