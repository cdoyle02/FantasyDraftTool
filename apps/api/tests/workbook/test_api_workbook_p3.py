"""HTTP tests for Workbook P3 pool rank + OL/DL routes."""

from __future__ import annotations

from draft_api.main import app
from draft_api.workbook.nflverse import PositionalWeekRate, ScheduledGame, WorkbookDataset
from draft_api.workbook.oldl import PassDropback
from draft_api.workbook.service import (
  clear_workbook_cache,
  set_workbook_dataset_override,
)
from draft_api.workbook.oldl import set_oldl_dropbacks_override

from fastapi.testclient import TestClient

client = TestClient(app)
SEASON = 2026
WEEK = 10


def _fixture_dataset() -> WorkbookDataset:
  all_wr_off = {
    ("AAA", w): PositionalWeekRate(targets=8, receptions=5, rec_yards=80, rec_tds=1)
    for w in (6, 7, 8, 9)
  }
  all_wr_def = {
    ("BBB", w): PositionalWeekRate(targets=5, receptions=3, rec_yards=30, rec_tds=0)
    for w in (6, 7, 8, 9)
  }
  return WorkbookDataset(
    season=SEASON,
    fetched_at="2026-11-08T12:00:00Z",
    teams=["AAA", "BBB"],
    schedule={w: {"AAA": "BBB", "BBB": "AAA"} for w in (6, 7, 8, 9, WEEK)},
    games=[ScheduledGame(week=WEEK, home="AAA", away="BBB", kickoff=None)],
    drives=[],
    pass_plays=[],
    team_env_off=[],
    team_env_def=[],
    positional_off={"all_wr": all_wr_off},
    positional_def={"all_wr": all_wr_def},
  )


def setup_function() -> None:
  clear_workbook_cache()
  set_workbook_dataset_override(_fixture_dataset())
  set_oldl_dropbacks_override(
    [
      PassDropback(week=9, offense="AAA", defense="BBB", sack=True, qb_hit=False, epa=-1.0),
      PassDropback(week=9, offense="AAA", defense="BBB", sack=False, qb_hit=False, epa=0.2),
    ]
  )


def teardown_function() -> None:
  set_oldl_dropbacks_override(None)
  set_workbook_dataset_override(None)
  clear_workbook_cache()


def test_workbook_pool_rank_defaults_half_ppr() -> None:
  response = client.post(
    "/api/v1/nfl/workbook/pool/rank",
    json={
      "week": WEEK,
      "window": "l4",
      "players": [{"name": "X", "team": "AAA", "salary": 5000, "position": "WR"}],
    },
    params={"season": SEASON},
  )
  assert response.status_code == 200
  body = response.json()
  assert body["scoring"] == "half_ppr"
  assert len(body["players"]) == 1
  assert body["players"][0]["joinStatus"] == "matched"


def test_workbook_pool_rank_rejects_large_pool() -> None:
  players = [
    {"name": f"P{i}", "team": "AAA", "salary": 4000, "position": "WR"} for i in range(501)
  ]
  response = client.post(
    "/api/v1/nfl/workbook/pool/rank",
    json={"week": WEEK, "players": players},
    params={"season": SEASON},
  )
  assert response.status_code == 400
  assert response.json()["error"]["code"] == "invalid_params"


def test_workbook_oldl_route() -> None:
  response = client.get(
    "/api/v1/nfl/workbook/oldl",
    params={"week": WEEK, "window": "custom", "startWeek": 9, "endWeek": 9, "season": SEASON},
  )
  assert response.status_code == 200
  body = response.json()
  assert body["source"] == "fixture"
  assert body["disclaimer"].startswith("OL/DL proxy")
  assert len(body["games"]) == 1
