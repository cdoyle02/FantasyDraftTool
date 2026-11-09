"""Task 5: Clay roles wired through load_workbook_dataset + snapshot."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from draft_api.sos.nflverse import SCHEDULES_URL, STATS_URL
from draft_api.workbook.clay_pdf import CLAY_PDF_URL_TEMPLATE, ClayWrRow
from draft_api.workbook.nflverse import PBP_URL, load_workbook_dataset
from draft_api.workbook.roles import build_role_index
from draft_api.workbook.service import (
    build_matchups_response,
    clear_workbook_cache,
    set_workbook_dataset_override,
)
from draft_api.workbook.snapshot import dataset_from_dict, write_snapshot

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


def test_load_workbook_dataset_persists_clay_roles() -> None:
    roles = _fixture_role_index()
    dataset = load_workbook_dataset(
        SEASON,
        http_get=_fake_http_get,
        now=datetime(2026, 11, 8, 12, 0, tzinfo=UTC),
        role_index=roles,
    )
    assert dataset.clay_roles == roles


def test_clay_pdf_failure_falls_back_to_previous_roles() -> None:
    clay_url = CLAY_PDF_URL_TEMPLATE.format(yy=SEASON % 100)
    previous = _fixture_role_index()

    def _get(url: str) -> bytes:
        if url == clay_url:
            raise RuntimeError("clay down")
        return _fake_http_get(url)

    dataset = load_workbook_dataset(
        SEASON,
        http_get=_get,
        now=datetime(2026, 11, 8, 12, 0, tzinfo=UTC),
        previous_clay_roles=previous,
    )
    assert dataset.clay_roles == previous
    assert dataset.positional_off["out_wr"][("KC", 5)].targets == pytest.approx(5.0)
    assert dataset.positional_off["slot_wr"][("KC", 5)].targets == pytest.approx(3.0)


def test_snapshot_clay_roles_round_trip(tmp_path) -> None:
    roles = _fixture_role_index()
    dataset = load_workbook_dataset(
        SEASON,
        http_get=_fake_http_get,
        role_index=roles,
    )
    path = tmp_path / "workbook_2026.json"
    write_snapshot(path, dataset)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["clayRoles"]
    restored = dataset_from_dict(payload)
    assert restored.clay_roles == roles


def test_matchups_out_and_slot_fp_non_null_with_clay_rates() -> None:
    """End-to-end service check: Clay-filled positional buckets → board cells."""
    roles = _fixture_role_index()
    dataset = load_workbook_dataset(
        SEASON,
        http_get=_fake_http_get,
        role_index=roles,
    )
    clear_workbook_cache()
    set_workbook_dataset_override(dataset)
    try:
        body = build_matchups_response(
            week=5,
            window="custom",
            scoring="ppr",
            slate="all",
            season=SEASON,
            custom_start_week=5,
            custom_end_week=5,
        )
        kc_row = next(
            row
            for game in body["games"]
            for row in game["rows"]
            if row["team"] == "KC"
        )
        assert kc_row["outWr"]["fpG"] == pytest.approx(16.0)
        assert kc_row["slotWr"]["fpG"] == pytest.approx(3.5)
        assert "reason" not in kc_row["outWr"]
        assert "reason" not in kc_row["slotWr"]
        assert "Mike Clay" in body["attribution"]
    finally:
        set_workbook_dataset_override(None)
        clear_workbook_cache()


def test_matchups_slot_null_without_clay_buckets() -> None:
    dataset = load_workbook_dataset(
        SEASON,
        http_get=_fake_http_get,
        role_index={},
    )
    clear_workbook_cache()
    set_workbook_dataset_override(dataset)
    try:
        body = build_matchups_response(
            week=5,
            window="custom",
            scoring="ppr",
            slate="all",
            season=SEASON,
            custom_start_week=5,
            custom_end_week=5,
        )
        kc_row = next(
            row
            for game in body["games"]
            for row in game["rows"]
            if row["team"] == "KC"
        )
        assert kc_row["outWr"] == {"fpG": None, "reason": "clay_unavailable"}
        assert kc_row["slotWr"] == {"fpG": None, "reason": "clay_unavailable"}
    finally:
        set_workbook_dataset_override(None)
        clear_workbook_cache()
