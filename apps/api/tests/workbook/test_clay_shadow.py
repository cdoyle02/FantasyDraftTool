"""Clay WR↔CB shadow parse + API assembly."""

from __future__ import annotations

from pathlib import Path

from draft_api.main import app
from draft_api.workbook.clay_pdf import parse_clay_shadow_layout_text
from draft_api.workbook.service import (
    build_clay_shadow_response,
    build_player_intel_response,
    clear_workbook_cache,
    set_clay_shadow_override,
    set_workbook_dataset_override,
)
from draft_api.workbook.nflverse import ScheduledGame, WorkbookDataset
from fastapi.testclient import TestClient

FIXTURE = Path(__file__).parent / "fixtures" / "clay_wrcb_week9_layout.txt"
client = TestClient(app)


def setup_function() -> None:
    clear_workbook_cache()
    set_clay_shadow_override(None)
    set_workbook_dataset_override(None)


def teardown_function() -> None:
    set_clay_shadow_override(None)
    set_workbook_dataset_override(None)
    clear_workbook_cache()


def test_parse_clay_shadow_layout() -> None:
    rows = parse_clay_shadow_layout_text(FIXTURE.read_text())
    assert len(rows) >= 10
    chase = next(r for r in rows if "Chase" in r.receiver)
    assert chase.offense_team == "CIN"
    assert chase.defender == "CJ Henderson"
    assert chase.defender_pos == "R"


def test_build_clay_shadow_response_override() -> None:
    rows = parse_clay_shadow_layout_text(FIXTURE.read_text())
    set_clay_shadow_override(rows)
    payload = build_clay_shadow_response(week=9, season=2026)
    assert payload["source"] == "clay_pdf"
    assert len(payload["shadows"]) == len(rows)
    assert payload["shadows"][0]["offenseTeam"] in {"ARI", "BAL", "BUF", "CAR", "CIN", "DAL", "DEN", "IND"}


def test_clay_shadow_route() -> None:
    set_clay_shadow_override(parse_clay_shadow_layout_text(FIXTURE.read_text()))
    response = client.get("/api/v1/nfl/workbook/clay-shadow", params={"week": 9})
    assert response.status_code == 200
    body = response.json()
    assert len(body["shadows"]) >= 10


def test_player_intel_includes_clay_shadow() -> None:
    set_workbook_dataset_override(
        WorkbookDataset(
            season=2026,
            fetched_at="2026-11-08T12:00:00Z",
            teams=["CIN", "ATL"],
            schedule={9: {"CIN": "ATL", "ATL": "CIN"}},
            games=[ScheduledGame(week=9, home="ATL", away="CIN", kickoff=None)],
            drives=[],
            pass_plays=[],
            team_env_off=[],
            team_env_def=[],
            positional_off={},
            positional_def={},
            clay_roles={"jamarr chase": "outside"},
        )
    )
    set_clay_shadow_override(parse_clay_shadow_layout_text(FIXTURE.read_text()))
    payload = build_player_intel_response(
        name="Ja'Marr Chase",
        week=9,
        team="CIN",
        season=2026,
    )
    assert payload["clayRole"] == "outside"
    assert payload["clayShadow"] is not None
    assert payload["clayShadow"]["defender"] == "CJ Henderson"
    assert payload["injury"] is None
    assert payload["sosOpportunity"] is None
    assert payload["ballersMention"] is None
