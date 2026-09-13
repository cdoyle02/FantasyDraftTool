from pathlib import Path

from draft_api.jared_k import (
    detect_week,
    fetch_jared_k_rankings,
    parse_jared_k_html,
)

FIXTURE = Path(__file__).parent / "fixtures" / "jared_k_week1.html"


def test_parse_jared_k_html_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    rows = parse_jared_k_html(html)
    assert rows[0].rank == 1
    assert rows[0].player == "Brandon Aubrey"
    assert rows[0].team == "DAL"
    assert "NYG" in rows[0].opponent
    assert rows[0].ecr == 1
    assert rows[3].player == "Jake Bates"
    assert rows[3].vs_ecr in ("+3", "3", "+3")
    assert len(rows) == 32


def test_detect_week_from_heading():
    html = FIXTURE.read_text(encoding="utf-8")
    assert detect_week(html) == 1


def test_fetch_jared_k_rankings_uses_http_get():
    html = FIXTURE.read_text(encoding="utf-8")

    def fake_get(url: str) -> str:
        assert "jared-smola.php" in url
        assert "position=K" in url
        assert "type=weekly" in url
        return html

    payload = fetch_jared_k_rankings(http_get=fake_get)
    assert payload["week"] == 1
    assert payload["rankings"][0]["player"] == "Brandon Aubrey"
    assert payload["rankings"][0]["rank"] == 1
    assert payload["rankings"][0]["team"] == "DAL"
