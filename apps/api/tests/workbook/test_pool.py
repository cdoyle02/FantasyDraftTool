"""DFS pool rank against Workbook Net matchup metrics."""

from __future__ import annotations

import pytest
from draft_api.workbook.nflverse import PositionalWeekRate, ScheduledGame, WorkbookDataset
from draft_api.workbook.pool import (
    PoolPlayerInput,
    rank_pool,
    row_to_json,
)

SEASON = 2026
WEEK = 10
WINDOW_WEEKS = {6, 7, 8, 9}


def _dataset() -> WorkbookDataset:
  """AAA vs BBB with WR offense/def rates favoring AAA."""
  all_wr_off: dict[tuple[str, int], PositionalWeekRate] = {}
  all_wr_def: dict[tuple[str, int], PositionalWeekRate] = {}
  for w in WINDOW_WEEKS:
    all_wr_off[("AAA", w)] = PositionalWeekRate(
      targets=10, receptions=7, rec_yards=100, rec_tds=2
    )
    all_wr_def[("BBB", w)] = PositionalWeekRate(
      targets=4, receptions=2, rec_yards=20, rec_tds=0
    )
    all_wr_off[("BBB", w)] = PositionalWeekRate(
      targets=6, receptions=4, rec_yards=40, rec_tds=0
    )
    all_wr_def[("AAA", w)] = PositionalWeekRate(
      targets=10, receptions=6, rec_yards=60, rec_tds=1
    )
  return WorkbookDataset(
    season=SEASON,
    fetched_at="2026-11-08T12:00:00Z",
    teams=["AAA", "BBB"],
    schedule={w: {"AAA": "BBB", "BBB": "AAA"} for w in (*WINDOW_WEEKS, WEEK)},
    games=[ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff=None)],
    drives=[],
    pass_plays=[],
    team_env_off=[],
    team_env_def=[],
    positional_off={"all_wr": all_wr_off},
    positional_def={"all_wr": all_wr_def},
  )


def test_rank_pool_gsis_id_index_recovers_wrong_csv_team() -> None:
  from draft_api.workbook.identity import PlayerIdIndex, PlayerRef

  dataset = _dataset()
  index = PlayerIdIndex.from_refs(
    [
      PlayerRef(
        gsis_id="00-0034829",
        espn_player_id=None,
        display_name="Stud",
        team="AAA",
      )
    ]
  )
  players = [
    PoolPlayerInput(
      name="Stud",
      team="ZZZ",  # wrong team in paste — gsis map recovers AAA
      salary=8000,
      position="WR",
      gsis_id="00-0034829",
    ),
  ]
  rows = rank_pool(
    players,
    dataset=dataset,
    week=WEEK,
    weeks=WINDOW_WEEKS,
    scoring="half_ppr",
    id_index=index,
  )
  assert rows[0].join_status == "matched"
  assert rows[0].team == "AAA"
  assert rows[0].matchup_team == "AAA"


def test_rank_pool_orders_by_value_then_net() -> None:
  dataset = _dataset()
  players = [
    PoolPlayerInput(name="Stud", team="AAA", salary=8000, position="WR"),
    PoolPlayerInput(name="Value", team="BBB", salary=4000, position="WR"),
    PoolPlayerInput(name="Unknown", team="ZZZ", salary=3000, position="WR"),
  ]
  rows = rank_pool(
    players,
    dataset=dataset,
    week=WEEK,
    weeks=WINDOW_WEEKS,
    scoring="half_ppr",
  )
  assert len(rows) == 3
  stud = next(r for r in rows if r.name == "Stud")
  value = next(r for r in rows if r.name == "Value")
  unknown = next(r for r in rows if r.name == "Unknown")
  assert stud.join_status == "matched"
  assert unknown.join_status == "unmatched"
  assert stud.net_fp_g is not None and value.net_fp_g is not None
  assert stud.value is not None and value.value is not None
  # AAA has softer WR net than BBB but Stud is expensive — Value should rank first.
  assert rows[0].name == "Value"
  assert rows[0].value is not None and rows[1].value is not None
  assert rows[0].value >= rows[1].value


def test_rank_pool_assigns_tertiles_within_pool() -> None:
  dataset = _dataset()
  players = [
    PoolPlayerInput(name="A", team="AAA", salary=5000, position="WR"),
    PoolPlayerInput(name="B", team="BBB", salary=5000, position="WR"),
  ]
  rows = rank_pool(
    players,
    dataset=dataset,
    week=WEEK,
    weeks=WINDOW_WEEKS,
    scoring="half_ppr",
  )
  tiers = {r.name: r.tier for r in rows}
  assert tiers["A"] in {"top", "mid", "bottom"}
  assert tiers["B"] in {"top", "mid", "bottom"}
  assert tiers["A"] != tiers["B"]


def test_row_to_json_camel_case() -> None:
  from draft_api.workbook.pool import PoolRankRow

  row = PoolRankRow(
    name="Jamarr Chase",
    team="AAA",
    salary=8200,
    position="WR",
    matchup_team="AAA",
    opponent="BBB",
    net_fp_g=12.5,
    tier="top",
    join_status="matched",
    value=1.524,
  )
  payload = row_to_json(row)
  assert payload["netFpG"] == 12.5
  assert payload["joinStatus"] == "matched"
  assert payload["matchupTeam"] == "AAA"

