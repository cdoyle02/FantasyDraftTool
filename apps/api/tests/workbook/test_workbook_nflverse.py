"""Parser tests for the Workbook nflverse loader (no network; fixture CSVs only)."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from draft_api.sos.nflverse import SCHEDULES_URL, STATS_URL
from draft_api.workbook.clay_pdf import ClayWrRow
from draft_api.workbook.roles import build_role_index
from draft_api.workbook.calculate import drive_success_rate, pass_rate_over_expectation
from draft_api.workbook.nflverse import (
    PBP_URL,
    WorkbookNflverseError,
    extract_drive_possessions,
    load_workbook_dataset,
    parse_alignment_csv,
    parse_play_by_play,
    parse_positional_stats,
)

FIXTURES = Path(__file__).parent / "fixtures"
SEASON = 2026


def _fixture_bytes(name: str, *, gzipped: bool) -> bytes:
    raw = (FIXTURES / name).read_bytes()
    return gzip.compress(raw) if gzipped else raw


def _fixture_role_index() -> dict[str, str]:
    raw = json.loads((FIXTURES / "clay_roles_mini.json").read_text())
    rows = [
        ClayWrRow(
            team=item["team"],
            name=item["name"],
            pos=item["pos"],  # type: ignore[arg-type]
            lwr_pct=item["lwr_pct"],
            slot_pct=item["slot_pct"],
            rwr_pct=item["rwr_pct"],
        )
        for item in raw
    ]
    return build_role_index(rows)


def _fake_http_get(url: str) -> bytes:
    if url == PBP_URL.format(season=SEASON):
        return _fixture_bytes("pbp_week5.csv", gzipped=True)
    if url == STATS_URL.format(season=SEASON):
        return _fixture_bytes("stats_player_week5.csv", gzipped=True)
    if url == SCHEDULES_URL:
        return _fixture_bytes("schedule.csv", gzipped=False)
    raise AssertionError(f"Unexpected URL requested: {url}")


def test_load_workbook_dataset_builds_env_drives_and_positional_rates() -> None:
    fixed_now = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    dataset = load_workbook_dataset(
        SEASON,
        http_get=_fake_http_get,
        now=fixed_now,
        role_index=_fixture_role_index(),
    )

    assert dataset.season == SEASON
    assert dataset.fetched_at == "2026-11-08T12:00:00Z"
    assert dataset.teams == ["BUF", "KC"]
    assert dataset.schedule[5] == {"BUF": "KC", "KC": "BUF"}

    # Drive success: 1 of 2 real drives succeeded; the kneel-only drive
    # (drive=3, qb_kneel=1) is dropped entirely rather than counted as a fail.
    assert drive_success_rate(dataset.drives, team="KC", weeks={5}) == pytest.approx(0.5)
    assert len(dataset.drives) == 2

    # PROE over the 4 non-kneel scrimmage plays, reusing the Task 2 helper
    # directly against the loader's raw `pass_plays` to cross-check
    # `team_env_off`'s own `proe` below.
    kc_proe = pass_rate_over_expectation(dataset.pass_plays, team="KC", weeks={5})
    assert kc_proe == pytest.approx(-1.25)
    assert len(dataset.pass_plays) == 4

    kc_off = next(s for s in dataset.team_env_off if s.team == "KC" and s.week == 5)
    assert kc_off.side == "off"
    assert kc_off.proe == pytest.approx(-1.25)
    assert kc_off.pass_plays == pytest.approx(2.0)
    assert kc_off.epa_pass == pytest.approx(0.2)
    assert kc_off.xplsv_pass == pytest.approx(0.5)
    assert kc_off.run_plays == pytest.approx(2.0)
    assert kc_off.epa_run == pytest.approx(0.075)
    assert kc_off.xplsv_run == pytest.approx(0.5)

    buf_def = next(s for s in dataset.team_env_def if s.team == "BUF" and s.week == 5)
    assert buf_def.side == "def"
    assert buf_def.proe == pytest.approx(-1.25)
    assert buf_def.pass_plays == pytest.approx(2.0)
    assert buf_def.epa_pass == pytest.approx(0.2)

    all_wr_off = dataset.positional_off["all_wr"][("KC", 5)]
    assert all_wr_off.targets == pytest.approx(8.0)
    assert all_wr_off.receptions == pytest.approx(6.0)
    assert all_wr_off.rec_yards == pytest.approx(75.0)
    assert all_wr_off.rec_tds == pytest.approx(1.0)
    assert all_wr_off.fantasy_points == pytest.approx(21.5)

    all_wr_def = dataset.positional_def["all_wr"][("BUF", 5)]
    assert all_wr_def.targets == pytest.approx(8.0)
    assert all_wr_def.fantasy_points == pytest.approx(21.5)

    qb_off = dataset.positional_off["qb"][("KC", 5)]
    assert qb_off.pass_yards == pytest.approx(250.0)
    assert qb_off.pass_tds == pytest.approx(2.0)

    rb_off = dataset.positional_off["rb"][("KC", 5)]
    assert rb_off.rush_att == pytest.approx(15.0)
    assert rb_off.rush_yards == pytest.approx(80.0)

    te_off = dataset.positional_off["te"][("KC", 5)]
    assert te_off.rec_yards == pytest.approx(30.0)

    # Out/Slot WR come from Clay roles + weekly stats (not PBP alignment).
    out_wr_off = dataset.positional_off["out_wr"][("KC", 5)]
    assert out_wr_off.targets == pytest.approx(5.0)
    assert out_wr_off.receptions == pytest.approx(4.0)
    assert out_wr_off.rec_yards == pytest.approx(60.0)
    assert out_wr_off.rec_tds == pytest.approx(1.0)
    assert out_wr_off.fantasy_points == pytest.approx(16.0)

    slot_wr_off = dataset.positional_off["slot_wr"][("KC", 5)]
    assert slot_wr_off.targets == pytest.approx(3.0)
    assert slot_wr_off.rec_yards == pytest.approx(15.0)
    assert slot_wr_off.fantasy_points == pytest.approx(3.5)

    out_wr_def = dataset.positional_def["out_wr"][("BUF", 5)]
    assert out_wr_def.rec_yards == pytest.approx(60.0)
    slot_wr_def = dataset.positional_def["slot_wr"][("BUF", 5)]
    assert slot_wr_def.rec_yards == pytest.approx(15.0)


def test_parse_alignment_csv_joins_on_nflverse_ids() -> None:
    text = (FIXTURES / "ftn_charting_week5.csv").read_text()
    joined = parse_alignment_csv(text)
    assert joined[("2026_05_KC_BUF", 101)] == "wide"
    assert joined[("2026_05_KC_BUF", 201)] == "slot"


def test_parse_alignment_csv_returns_empty_when_column_absent() -> None:
    # Mirrors the real public `ftn_charting` release, which has no receiver
    # alignment column at all (see module docstring in `nflverse.py`).
    text = (
        "ftn_game_id,nflverse_game_id,season,week,ftn_play_id,nflverse_play_id,is_motion\n"
        "9001,2026_05_KC_BUF,2026,5,500001,101,FALSE\n"
    )
    assert parse_alignment_csv(text) == {}


def test_http_get_failure_raises_workbook_nflverse_error() -> None:
    def _boom(url: str) -> bytes:
        raise RuntimeError("network down")

    with pytest.raises(WorkbookNflverseError):
        load_workbook_dataset(SEASON, http_get=_boom)


def test_parse_positional_stats_rejects_missing_required_headers() -> None:
    text = "season,week,position\n2026,5,WR\n"
    with pytest.raises(WorkbookNflverseError, match="missing required columns"):
        parse_positional_stats(text, season=SEASON)


def test_parse_positional_stats_rejects_invalid_numeric_values() -> None:
    text = (FIXTURES / "stats_player_week5.csv").read_text()
    bad = text.replace("16.0", "not-a-number", 1)
    with pytest.raises(WorkbookNflverseError, match="invalid numeric value"):
        parse_positional_stats(bad, season=SEASON)


def test_extract_drive_possessions_from_pbp_top_fixture() -> None:
    text = (FIXTURES / "pbp_top_mini.csv").read_text()
    drives = extract_drive_possessions(text, season=SEASON)
    assert len(drives) == 4
    aaa = sum(d.seconds for d in drives if d.team == "AAA")
    bbb = sum(d.seconds for d in drives if d.team == "BBB")
    assert aaa == 300.0
    assert bbb == 240.0


def test_extract_drive_possessions_absent_column_returns_empty() -> None:
    text = (FIXTURES / "pbp_week5.csv").read_text()
    assert extract_drive_possessions(text, season=SEASON) == []


def test_parse_play_by_play_rejects_missing_required_headers() -> None:
    text = "season,week,posteam\n2026,5,KC\n"
    with pytest.raises(WorkbookNflverseError, match="missing required columns"):
        parse_play_by_play(
            text,
            season=SEASON,
            player_position={},
            alignment_by_key={},
        )


def test_parse_play_by_play_rejects_invalid_optional_numeric_fields() -> None:
    text = (FIXTURES / "pbp_week5.csv").read_text()
    bad = text.replace("0.5", "bad-epa", 1)
    with pytest.raises(WorkbookNflverseError, match="invalid numeric value for epa"):
        parse_play_by_play(
            bad,
            season=SEASON,
            player_position={"WR1": "WR", "WR2": "WR"},
            alignment_by_key={},
        )


def test_load_workbook_dataset_rejects_missing_schedule_headers() -> None:
    def _get_bad_schedule(url: str) -> bytes:
        if url == SCHEDULES_URL:
            return b"season,week\n2026,5\n"
        return _fake_http_get(url)

    with pytest.raises(WorkbookNflverseError, match="schedules: missing required columns"):
        load_workbook_dataset(SEASON, http_get=_get_bad_schedule)


def test_default_http_get_wraps_network_errors() -> None:
    # No real network use: port 1 on localhost refuses instantly, so this
    # stays fast and offline-safe while proving errors surface as
    # WorkbookNflverseError rather than a raw urllib exception.
    from draft_api.workbook.nflverse import default_http_get

    with pytest.raises(WorkbookNflverseError):
        default_http_get("http://127.0.0.1:1/")
