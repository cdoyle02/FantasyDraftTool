from pathlib import Path

from draft_api.kyle_dst import (
    detect_week,
    fetch_kyle_dst_rankings,
    parse_kyle_dst_html,
    team_abbrev_from_name,
)

FIXTURE = Path(__file__).parent / "fixtures" / "kyle_dst_week1.html"


def test_parse_kyle_dst_html_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_kyle_dst_html(html)
    assert rows[0].rank == 1
    assert rows[0].team == "JAX"
    assert rows[0].team_name == "Jacksonville Jaguars"
    assert "CLE" in rows[0].opponent
    assert rows[0].ecr == 1
    assert rows[2].team == "TEN"
    assert rows[2].vs_ecr in ("+7", "7", "+7")
    assert len(rows) == 32


def test_detect_week_from_heading():
    html = FIXTURE.read_text(encoding="utf-8")
    assert detect_week(html) == 1


def test_team_abbrev_from_name():
    assert team_abbrev_from_name("Kansas City Chiefs") == "KC"
    assert team_abbrev_from_name("Los Angeles Chargers") == "LAC"


def test_fetch_kyle_dst_rankings_uses_http_get():
    html = FIXTURE.read_text(encoding="utf-8")

    def fake_get(url: str) -> str:
        assert "kyle-krajewski.php" in url
        assert "position=DST" in url
        return html

    payload = fetch_kyle_dst_rankings(http_get=fake_get)
    assert payload["week"] == 1
    assert payload["rankings"][0]["team"] == "JAX"
    assert payload["rankings"][0]["rank"] == 1
