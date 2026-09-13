"""The Odds API adapter implementing OddsProvider."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from draft_api.implied_totals import GameLine

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
NFL_SPORT_KEY = "americanfootball_nfl"
PREFERRED_BOOKS = ("draftkings", "fanduel")

# Full team name (The Odds API) → standard NFL abbrev used in this app.
TEAM_ABBREV: dict[str, str] = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


HttpGetter = Callable[[str], bytes]


class OddsApiError(RuntimeError):
    """Raised when The Odds API request fails or returns unusable data."""


def team_abbrev(name: str) -> str:
    return TEAM_ABBREV.get(name, name)


def _parse_commence(value: str) -> datetime:
    # Odds API returns ISO8601 with Z suffix.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _market_outcomes(bookmaker: dict[str, Any], market_key: str) -> list[dict[str, Any]] | None:
    for market in bookmaker.get("markets") or []:
        if market.get("key") == market_key:
            return list(market.get("outcomes") or [])
    return None


def _spread_and_total_from_book(
    bookmaker: dict[str, Any],
    *,
    home_name: str,
    away_name: str,
) -> tuple[float, float, str, str] | None:
    """Return (spread_home_perspective, total, favorite, underdog) or None."""
    spreads = _market_outcomes(bookmaker, "spreads")
    totals = _market_outcomes(bookmaker, "totals")
    if not spreads or not totals:
        return None

    home_point: float | None = None
    away_point: float | None = None
    for outcome in spreads:
        name = outcome.get("name")
        point = outcome.get("point")
        if point is None:
            continue
        if name == home_name:
            home_point = float(point)
        elif name == away_name:
            away_point = float(point)
    if home_point is None and away_point is None:
        return None
    # Prefer home side point; if only away present, negate for home perspective.
    if home_point is not None:
        spread = home_point
    else:
        spread = -float(away_point)  # type: ignore[arg-type]

    total_point: float | None = None
    for outcome in totals:
        if outcome.get("name") == "Over" and outcome.get("point") is not None:
            total_point = float(outcome["point"])
            break
        if outcome.get("point") is not None and total_point is None:
            total_point = float(outcome["point"])
    if total_point is None:
        return None

    if spread < 0:
        favorite, underdog = home_name, away_name
    elif spread > 0:
        favorite, underdog = away_name, home_name
    else:
        # Pick'em: treat home as nominal favorite for D/ST ranking.
        favorite, underdog = home_name, away_name

    return spread, total_point, favorite, underdog


def consensus_line(event: dict[str, Any]) -> GameLine | None:
    """Build a GameLine from DK/FD average when possible, else first usable book."""
    home_name = str(event.get("home_team") or "")
    away_name = str(event.get("away_team") or "")
    commence_raw = event.get("commence_time")
    if not home_name or not away_name or not commence_raw:
        return None

    bookmakers = list(event.get("bookmakers") or [])
    by_key = {str(b.get("key")): b for b in bookmakers if b.get("key")}

    preferred_rows: list[tuple[float, float, str, str]] = []
    for key in PREFERRED_BOOKS:
        book = by_key.get(key)
        if not book:
            continue
        row = _spread_and_total_from_book(book, home_name=home_name, away_name=away_name)
        if row:
            preferred_rows.append(row)

    if len(preferred_rows) >= 2:
        spread = sum(r[0] for r in preferred_rows) / len(preferred_rows)
        total = sum(r[1] for r in preferred_rows) / len(preferred_rows)
        # Re-derive favorite from averaged spread.
        if spread < 0:
            favorite, underdog = home_name, away_name
        elif spread > 0:
            favorite, underdog = away_name, home_name
        else:
            favorite, underdog = home_name, away_name
        bookmaker = "consensus"
    elif preferred_rows:
        spread, total, favorite, underdog = preferred_rows[0]
        bookmaker = next(
            (k for k in PREFERRED_BOOKS if k in by_key),
            "consensus",
        )
    else:
        fallback: tuple[float, float, str, str] | None = None
        bookmaker = "unknown"
        for book in bookmakers:
            row = _spread_and_total_from_book(book, home_name=home_name, away_name=away_name)
            if row:
                fallback = row
                bookmaker = str(book.get("key") or "unknown")
                break
        if fallback is None:
            return None
        spread, total, favorite, underdog = fallback

    return GameLine(
        home_team=team_abbrev(home_name),
        away_team=team_abbrev(away_name),
        commence_time=_parse_commence(str(commence_raw)),
        spread=spread,
        total=total,
        favorite_team=team_abbrev(favorite),
        underdog_team=team_abbrev(underdog),
        bookmaker=bookmaker,
    )


def default_http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OddsApiError(f"The Odds API HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise OddsApiError(f"The Odds API request failed: {exc.reason}") from exc


class TheOddsApiProvider:
    """OddsProvider backed by api.the-odds-api.com."""

    def __init__(
        self,
        api_key: str,
        *,
        http_get: HttpGetter | None = None,
        regions: str = "us",
        markets: str = "spreads,totals",
    ) -> None:
        if not api_key.strip():
            raise OddsApiError("ODDS_API_KEY is empty")
        self._api_key = api_key.strip()
        self._http_get = http_get or default_http_get
        self._regions = regions
        self._markets = markets

    def fetch_nfl_odds(self) -> list[GameLine]:
        query = urllib.parse.urlencode(
            {
                "apiKey": self._api_key,
                "regions": self._regions,
                "markets": self._markets,
                "oddsFormat": "american",
            }
        )
        url = f"{ODDS_API_BASE}/sports/{NFL_SPORT_KEY}/odds/?{query}"
        raw = self._http_get(url)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OddsApiError("The Odds API returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise OddsApiError("The Odds API returned an unexpected payload")

        games: list[GameLine] = []
        for event in payload:
            if not isinstance(event, dict):
                continue
            line = consensus_line(event)
            if line is not None:
                games.append(line)
        return games
