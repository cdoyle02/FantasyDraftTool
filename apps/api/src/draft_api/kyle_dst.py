"""Scrape Kyle Krajewski weekly DST rankings from FantasyPros."""

from __future__ import annotations

import html as html_lib
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from draft_api.odds.the_odds_api import TEAM_ABBREV

BASE_URL = "https://www.fantasypros.com/nfl/rankings/kyle-krajewski.php"
USER_AGENT = (
    "Mozilla/5.0 (compatible; FantasyDraftTool/1.0; "
    "+https://www.fantasypros.com/nfl/rankings/kyle-krajewski.php)"
)

# Reverse map full team name → abbrev (Odds API table already has full names).
_NAME_TO_ABBREV = {name: abbrev for name, abbrev in TEAM_ABBREV.items()}
# FantasyPros sometimes uses slightly different labels.
_NAME_TO_ABBREV.update(
    {
        "Washington Football Team": "WAS",
        "Washington Redskins": "WAS",
    }
)


class KyleDstError(RuntimeError):
    """Raised when FantasyPros scrape fails or returns no usable rows."""


@dataclass(frozen=True, slots=True)
class KyleDstRow:
    rank: int
    team: str
    team_name: str
    opponent: str
    ecr: int | None
    vs_ecr: str


HttpGetter = Callable[[str], str]


def build_url(*, week: int | None = None) -> str:
    params: dict[str, str] = {
        "type": "weekly",
        "scoring": "STD",
        "position": "DST",
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
        raise KyleDstError(f"FantasyPros HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise KyleDstError(f"FantasyPros request failed: {exc.reason}") from exc


def detect_week(html: str, *, requested: int | None = None) -> int | None:
    if requested is not None:
        return requested
    m = re.search(r"DST Rankings\s*-\s*Week\s+(\d+)", html, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"week\s+(\d+)\s+outlook", html, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"[?&]week=(\d+)", html)
    if m:
        return int(m.group(1))
    return None


def team_abbrev_from_name(name: str) -> str:
    cleaned = html_lib.unescape(name).strip()
    if cleaned in _NAME_TO_ABBREV:
        return _NAME_TO_ABBREV[cleaned]
    # Fallback: last token heuristics already covered; keep raw short label.
    return cleaned


def _optional_int(value: str) -> int | None:
    text = html_lib.unescape(value).strip()
    if not text or not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def parse_kyle_dst_html(html: str) -> list[KyleDstRow]:
    """Parse Rank | Team | Opp | ECR | vs ECR table rows."""
    # Pull the rankings table body (id="data" on FantasyPros expert pages).
    table_match = re.search(
        r'<table[^>]*id="data"[^>]*>(.*?)</table>',
        html,
        flags=re.I | re.S,
    )
    body = table_match.group(1) if table_match else html
    rows: list[KyleDstRow] = []
    for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1), flags=re.I | re.S)
        if len(cells) < 5:
            continue
        rank_text = re.sub(r"<[^>]+>", "", cells[0])
        rank_text = html_lib.unescape(rank_text).strip()
        if not rank_text.isdigit():
            continue
        name_html = cells[1]
        name_match = re.search(r"<a[^>]*>(.*?)</a>", name_html, flags=re.I | re.S)
        team_name = html_lib.unescape(
            re.sub(r"<[^>]+>", "", name_match.group(1) if name_match else name_html)
        ).strip()
        team_name = re.sub(r"\s+", " ", team_name)
        if not team_name:
            continue
        opponent = html_lib.unescape(re.sub(r"<[^>]+>", "", cells[2])).strip()
        opponent = re.sub(r"\s+", " ", opponent)
        ecr = _optional_int(re.sub(r"<[^>]+>", "", cells[3]))
        vs_ecr = html_lib.unescape(re.sub(r"<[^>]+>", "", cells[4])).strip()
        vs_ecr = re.sub(r"\s+", " ", vs_ecr)
        rows.append(
            KyleDstRow(
                rank=int(rank_text),
                team=team_abbrev_from_name(team_name),
                team_name=team_name,
                opponent=opponent,
                ecr=ecr,
                vs_ecr=vs_ecr,
            )
        )
    if not rows:
        raise KyleDstError("No DST ranking rows found — page markup may have changed.")
    rows.sort(key=lambda row: row.rank)
    return rows


def fetch_kyle_dst_rankings(
    *,
    week: int | None = None,
    http_get: HttpGetter | None = None,
) -> dict[str, Any]:
    """Fetch and normalize Kyle weekly DST rankings."""
    getter = http_get or default_http_get
    url = build_url(week=week)
    html = getter(url)
    detected = detect_week(html, requested=week)
    rankings = parse_kyle_dst_html(html)
    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "week": detected,
        "fetchedAt": fetched_at,
        "sourceUrl": url,
        "rankings": [
            {
                "rank": row.rank,
                "team": row.team,
                "teamName": row.team_name,
                "opponent": row.opponent,
                "ecr": row.ecr,
                "vsEcr": row.vs_ecr,
            }
            for row in rankings
        ],
    }
