"""ESPN injuries normalization (fixture only)."""

from __future__ import annotations

import json
from pathlib import Path

from draft_api.workbook.injuries import fetch_week_injuries, parse_injuries_from_roster_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAYLOAD = json.loads((FIXTURES / "espn_injuries_mini.json").read_text(encoding="utf-8"))


def test_parse_injuries_skips_healthy_and_sorts_by_severity() -> None:
    rows = parse_injuries_from_roster_payload(PAYLOAD)
    assert len(rows) == 3
    assert rows[0].status == "O"
    assert rows[1].status == "D"
    assert rows[2].status == "Q"
    assert rows[0].body_part == "Knee"
    assert rows[2].practice == "Limited"


def test_fetch_week_injuries_uses_http_override() -> None:
    def fake_http(url: str, headers: dict[str, str]) -> dict:
        assert "mRoster" in url or "view=" in url
        assert headers["Cookie"]
        return PAYLOAD

    rows = fetch_week_injuries(
        league_id="1216398267",
        season=2026,
        week=10,
        espn_s2="s2",
        swid="{SWID}",
        http_json=fake_http,
    )
    assert len(rows) == 3
    assert rows[0].name == "Player Out"
