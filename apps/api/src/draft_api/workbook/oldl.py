"""OL/DL proxy metrics from nflverse pass-dropback samples (not Football Outsiders)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from draft_api.workbook.nflverse import WorkbookDataset

OLDL_DISCLAIMER = (
  "OL/DL proxy from nflverse; not Football Outsiders."
)

_dropbacks_override: list["PassDropback"] | None = None


@dataclass(frozen=True, slots=True)
class PassDropback:
  week: int
  offense: str
  defense: str
  sack: bool = False
  qb_hit: bool = False
  epa: float | None = None


@dataclass(frozen=True, slots=True)
class OldlTeamRow:
  team: str
  pressure_rate_allowed: float | None
  sack_rate_allowed: float | None
  epa_per_dropback_allowed: float | None
  rank_pressure: int | None


def set_oldl_dropbacks_override(dropbacks: list[PassDropback] | None) -> None:
  """Test hook: inject dropback samples instead of deriving from the dataset."""
  global _dropbacks_override
  _dropbacks_override = dropbacks


def _pressure(dropback: PassDropback) -> bool:
  return dropback.sack or dropback.qb_hit


def _aggregate_offense_dropbacks(
  dropbacks: list[PassDropback],
  *,
  weeks: set[int],
) -> dict[str, tuple[int, int, int, float, int]]:
  """team -> (dropbacks, pressures, sacks, epa_sum, epa_n)."""
  stats: dict[str, list[PassDropback]] = defaultdict(list)
  for play in dropbacks:
    if play.week not in weeks:
      continue
    stats[play.offense].append(play)

  out: dict[str, tuple[int, int, int, float, int]] = {}
  for team, plays in stats.items():
    dropback_n = len(plays)
    pressures = sum(1 for p in plays if _pressure(p))
    sacks = sum(1 for p in plays if p.sack)
    epa_sum = 0.0
    epa_n = 0
    for play in plays:
      if play.epa is not None:
        epa_sum += play.epa
        epa_n += 1
    out[team] = (dropback_n, pressures, sacks, epa_sum, epa_n)
  return out


def _dropbacks_from_team_env(
  dataset: WorkbookDataset,
  *,
  weeks: set[int],
) -> list[PassDropback]:
  """Fallback: one synthetic dropback per counted pass play with team EPA."""
  epa_by_team_week: dict[tuple[str, int], float | None] = {}
  for sl in dataset.team_env_off:
    if sl.week in weeks:
      epa_by_team_week[(sl.team, sl.week)] = sl.epa_pass

  dropbacks: list[PassDropback] = []
  for sl in dataset.team_env_off:
    if sl.week not in weeks or sl.pass_plays is None:
      continue
    count = int(sl.pass_plays)
    if count <= 0:
      continue
    opponent = (dataset.schedule.get(sl.week) or {}).get(sl.team)
    if not opponent:
      continue
    epa = epa_by_team_week.get((sl.team, sl.week))
    per_play_epa = epa if epa is not None else None
    for _ in range(count):
      dropbacks.append(
        PassDropback(
          week=sl.week,
          offense=sl.team,
          defense=opponent,
          sack=False,
          qb_hit=False,
          epa=per_play_epa,
        )
      )
  return dropbacks


def resolve_dropbacks(dataset: WorkbookDataset, *, weeks: set[int]) -> list[PassDropback]:
  if _dropbacks_override is not None:
    return _dropbacks_override
  return _dropbacks_from_team_env(dataset, weeks=weeks)


def build_oldl_team_rows(
  dataset: WorkbookDataset,
  *,
  weeks: set[int],
  dropbacks: list[PassDropback] | None = None,
) -> list[OldlTeamRow]:
  plays = dropbacks if dropbacks is not None else resolve_dropbacks(dataset, weeks=weeks)
  aggregated = _aggregate_offense_dropbacks(plays, weeks=weeks)

  preliminary: list[OldlTeamRow] = []
  for team in dataset.teams:
    sample = aggregated.get(team)
    if sample is None:
      preliminary.append(
        OldlTeamRow(
          team=team,
          pressure_rate_allowed=None,
          sack_rate_allowed=None,
          epa_per_dropback_allowed=None,
          rank_pressure=None,
        )
      )
      continue
    dropback_n, pressures, sacks, epa_sum, epa_n = sample
    pressure_rate = (pressures / dropback_n) if dropback_n else None
    sack_rate = (sacks / dropback_n) if dropback_n else None
    epa_per = (epa_sum / epa_n) if epa_n else None
    preliminary.append(
      OldlTeamRow(
        team=team,
        pressure_rate_allowed=round(pressure_rate, 4) if pressure_rate is not None else None,
        sack_rate_allowed=round(sack_rate, 4) if sack_rate is not None else None,
        epa_per_dropback_allowed=round(epa_per, 4) if epa_per is not None else None,
        rank_pressure=None,
      )
    )

  ranked = [
    row
    for row in preliminary
    if row.pressure_rate_allowed is not None
  ]
  ranked.sort(key=lambda row: (row.pressure_rate_allowed, row.team))
  rank_map = {row.team: index + 1 for index, row in enumerate(ranked)}

  return [
    OldlTeamRow(
      team=row.team,
      pressure_rate_allowed=row.pressure_rate_allowed,
      sack_rate_allowed=row.sack_rate_allowed,
      epa_per_dropback_allowed=row.epa_per_dropback_allowed,
      rank_pressure=rank_map.get(row.team),
    )
    for row in preliminary
  ]


def row_to_json(row: OldlTeamRow) -> dict[str, object]:
  return {
    "team": row.team,
    "pressureRateAllowed": row.pressure_rate_allowed,
    "sackRateAllowed": row.sack_rate_allowed,
    "epaPerDropbackAllowed": row.epa_per_dropback_allowed,
    "rankPressure": row.rank_pressure,
  }


def build_oldl_games(
  dataset: WorkbookDataset,
  *,
  week: int,
  team_rows: dict[str, OldlTeamRow],
) -> list[dict[str, Any]]:
  """One game row with offense OL vs defense DL proxy columns."""
  games: list[dict[str, Any]] = []
  for game in sorted(
    (g for g in dataset.games if g.week == week),
    key=lambda g: (g.kickoff or "", g.home),
  ):
    rows: list[dict[str, object]] = []
    for team, role in ((game.home, "offense_ol"), (game.away, "defense_dl")):
      metric_row = team_rows.get(team)
      payload = row_to_json(metric_row) if metric_row else row_to_json(
        OldlTeamRow(team, None, None, None, None)
      )
      payload["role"] = role
      rows.append(payload)
    games.append({"home": game.home, "away": game.away, "kickoff": game.kickoff, "rows": rows})
  return games
