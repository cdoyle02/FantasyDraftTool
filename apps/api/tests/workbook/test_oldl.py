"""OL/DL proxy tab metrics from PBP dropback samples."""

from __future__ import annotations

import pytest
from draft_api.workbook.nflverse import ScheduledGame, WorkbookDataset
from draft_api.workbook.oldl import (
    PassDropback,
    build_oldl_games,
    build_oldl_team_rows,
    row_to_json,
)

WEEK = 9


def _dataset() -> WorkbookDataset:
  return WorkbookDataset(
    season=2026,
    fetched_at="2026-11-08T12:00:00Z",
    teams=["AAA", "BBB"],
    schedule={WEEK: {"AAA": "BBB", "BBB": "AAA"}},
    games=[ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff=None)],
    drives=[],
    pass_plays=[],
    team_env_off=[],
    team_env_def=[],
    positional_off={},
    positional_def={},
  )


def _dropbacks() -> list[PassDropback]:
  return [
    PassDropback(week=WEEK, offense="AAA", defense="BBB", sack=False, qb_hit=True, epa=0.1),
    PassDropback(week=WEEK, offense="AAA", defense="BBB", sack=True, qb_hit=False, epa=-2.0),
    PassDropback(week=WEEK, offense="AAA", defense="BBB", sack=False, qb_hit=False, epa=0.5),
    PassDropback(week=WEEK, offense="AAA", defense="BBB", sack=False, qb_hit=False, epa=0.2),
    PassDropback(week=WEEK, offense="BBB", defense="AAA", sack=False, qb_hit=False, epa=-0.1),
    PassDropback(week=WEEK, offense="BBB", defense="AAA", sack=False, qb_hit=False, epa=0.0),
  ]


def test_build_oldl_team_rows_pressure_and_epa() -> None:
  dataset = _dataset()
  rows = build_oldl_team_rows(
    dataset,
    weeks={WEEK},
    dropbacks=_dropbacks(),
  )
  aaa = next(r for r in rows if r.team == "AAA")
  bbb = next(r for r in rows if r.team == "BBB")
  assert aaa.pressure_rate_allowed == pytest.approx(0.5)
  assert aaa.sack_rate_allowed == pytest.approx(0.25)
  assert aaa.epa_per_dropback_allowed == pytest.approx(-0.3, abs=0.01)
  assert bbb.pressure_rate_allowed == pytest.approx(0.0)
  assert bbb.rank_pressure == 1
  assert aaa.rank_pressure == 2


def test_build_oldl_games_pairs_matchups() -> None:
  dataset = _dataset()
  team_rows = {r.team: r for r in build_oldl_team_rows(dataset, weeks={WEEK}, dropbacks=_dropbacks())}
  games = build_oldl_games(dataset, week=WEEK, team_rows=team_rows)
  assert len(games) == 1
  game = games[0]
  assert game["home"] == "AAA"
  assert game["away"] == "BBB"
  home_row = next(r for r in game["rows"] if r["team"] == "AAA")
  away_row = next(r for r in game["rows"] if r["team"] == "BBB")
  assert home_row["role"] == "offense_ol"
  assert away_row["role"] == "defense_dl"
  assert home_row["pressureRateAllowed"] == row_to_json(team_rows["AAA"])["pressureRateAllowed"]


def test_row_to_json_camel_case() -> None:
  from draft_api.workbook.oldl import OldlTeamRow

  row = OldlTeamRow(
    team="KC",
    pressure_rate_allowed=0.2,
    sack_rate_allowed=0.05,
    epa_per_dropback_allowed=0.01,
    rank_pressure=3,
  )
  payload = row_to_json(row)
  assert payload["pressureRateAllowed"] == 0.2
  assert payload["rankPressure"] == 3
