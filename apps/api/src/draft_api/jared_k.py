"""Scrape Jared Smola weekly K rankings from FantasyPros."""

from __future__ import annotations

import html as html_lib
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

BASE_URL = "https://www.fantasypros.com/nfl/rankings/jared-smola.php"
USER_AGENT = (
    "Mozilla/5.0 (compatible; FantasyDraftTool/1.0; "
    "+https://www.fantasypros.com/nfl/rankings/jared-smola.php)"
)


class JaredKError(RuntimeError):
    """Raised when FantasyPros scrape fails or returns no usable rows."""


@dataclass(frozen=True, slots=True)
class JaredKRow:
    rank: int
    player: str
    team: str
    opponent: str
    ecr: int | None
    vs_ecr: str


HttpGetter = Callable[[str], str]


def build_url(*, week: int | None = None) -> str:
    params: dict[str, str] = {
        "type": "weekly",
        "scoring": "STD",
        "position": "K",
    }
    if week is not None:
        params["week"] = str(week)
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def default_http_get(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise JaredKError(f"FantasyPros HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise JaredKError(f"FantasyPros request failed: {exc.reason}") from exc


def detect_week(html: str, *, requested: int | None = None) -> int | None:
    if requested is not None:
        return requested
    m = re.search(r"K Rankings\s*-\s*Week\s+(\d+)", html, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"week\s+(\d+)\s+outlook", html, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"[?&]week=(\d+)", html)
    if m:
        return int(m.group(1))
    return None


def _optional_int(value: str) -> int | None:
    text = html_lib.unescape(value).strip()
    if not text or not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def _cell_text(cell_html: str) -> str:
    text = html_lib.unescape(re.sub(r"<[^>]+>", "", cell_html)).strip()
    return re.sub(r"\s+", " ", text)


def parse_jared_k_html(html: str) -> list[JaredKRow]:
    """Parse Rank | Player | Team | Opp | ECR | vs ECR table rows."""
    table_match = re.search(
        r'<table[^>]*id="data"[^>]*>(.*?)</table>',
        html,
        flags=re.I | re.S,
    )
    body = table_match.group(1) if table_match else html
    rows: list[JaredKRow] = []
    for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1), flags=re.I | re.S)
        if len(cells) < 6:
            continue
        rank_text = _cell_text(cells[0])
        if not rank_text.isdigit():
            continue
        name_attr = re.search(
            r'fp-player-name="([^"]+)"',
            cells[1],
            flags=re.I,
        )
        if name_attr:
            player = html_lib.unescape(name_attr.group(1)).strip()
        else:
            name_match = re.search(r"<a[^>]*>(.*?)</a>", cells[1], flags=re.I | re.S)
            player = _cell_text(name_match.group(1) if name_match else cells[1])
        player = re.sub(r"\s+", " ", player)
        if not player:
            continue
        team = _cell_text(cells[2]).upper()
        opponent = _cell_text(cells[3])
        ecr = _optional_int(_cell_text(cells[4]))
        vs_ecr = _cell_text(cells[5])
        rows.append(
            JaredKRow(
                rank=int(rank_text),
                player=player,
                team=team,
                opponent=opponent,
                ecr=ecr,
                vs_ecr=vs_ecr,
            )
        )
    if not rows:
        raise JaredKError("No kicker ranking rows found — page markup may have changed.")
    rows.sort(key=lambda row: row.rank)
    return rows


def fetch_jared_k_rankings(
    *,
    week: int | None = None,
    http_get: HttpGetter | None = None,
) -> dict[str, Any]:
    """Fetch and normalize Jared weekly K rankings."""
    getter = http_get or default_http_get
    url = build_url(week=week)
    html = getter(url)
    detected = detect_week(html, requested=week)
    rankings = parse_jared_k_html(html)
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "week": detected,
        "fetchedAt": fetched_at,
        "sourceUrl": url,
        "rankings": [
            {
                "rank": row.rank,
                "player": row.player,
                "team": row.team,
                "opponent": row.opponent,
                "ecr": row.ecr,
                "vsEcr": row.vs_ecr,
            }
            for row in rankings
        ],
    }
