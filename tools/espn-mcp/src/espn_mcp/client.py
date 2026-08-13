"""HTTP access to ESPN's fantasy football v3 read endpoints."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from .reference import READS_HOST

# Cookies live in tools/espn-mcp/.env so they stay out of both the MCP client
# config and version control.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_SEASON = 2026
USER_AGENT = "Mozilla/5.0 (compatible; fantasy-draft-tool-espn-mcp)"


class EspnError(RuntimeError):
    """Raised for configuration or upstream failures worth showing to the model."""


@dataclass(frozen=True)
class EspnConfig:
    season: int
    league_id: str | None
    espn_s2: str | None
    swid: str | None

    @property
    def authenticated(self) -> bool:
        return bool(self.espn_s2 and self.swid)

    def cookies(self) -> dict[str, str]:
        if not self.authenticated:
            return {}
        assert self.espn_s2 is not None and self.swid is not None
        return {"espn_s2": self.espn_s2, "SWID": self.swid}

    def secrets(self) -> list[str]:
        return [value for value in (self.espn_s2, self.swid) if value]


def load_config() -> EspnConfig:
    """Read configuration from the environment.

    Credentials are deliberately never accepted as tool arguments so that cookie
    values cannot end up in a model transcript.
    """
    raw_season = os.environ.get("ESPN_SEASON", "").strip()
    try:
        season = int(raw_season) if raw_season else DEFAULT_SEASON
    except ValueError as error:
        raise EspnError(f"ESPN_SEASON must be a year, got {raw_season!r}") from error

    swid = os.environ.get("ESPN_SWID", "").strip() or None
    if swid and not swid.startswith("{"):
        swid = "{" + swid.strip("{}") + "}"

    return EspnConfig(
        season=season,
        league_id=os.environ.get("ESPN_LEAGUE_ID", "").strip() or None,
        espn_s2=os.environ.get("ESPN_S2", "").strip() or None,
        swid=swid,
    )


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return text


def league_url(season: int, league_id: str) -> str:
    if season <= 2017:
        return f"{READS_HOST}/apis/v3/games/ffl/leagueHistory/{league_id}"
    return f"{READS_HOST}/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{league_id}"


def season_players_url(season: int) -> str:
    return f"{READS_HOST}/apis/v3/games/ffl/seasons/{season}/players"


def season_meta_url(season: int) -> str:
    return f"{READS_HOST}/apis/v3/games/ffl/seasons/{season}"


async def fetch(
    url: str,
    *,
    config: EspnConfig,
    views: list[str] | None = None,
    params: dict[str, Any] | None = None,
    fantasy_filter: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    query: list[tuple[str, str]] = []
    for key, value in (params or {}).items():
        if value is not None:
            query.append((key, str(value)))
    for view in views or []:
        query.append(("view", view))
    if config.season <= 2017 and "leagueHistory" in url:
        query.append(("seasonId", str(config.season)))

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if fantasy_filter:
        headers["X-Fantasy-Filter"] = json.dumps(fantasy_filter, separators=(",", ":"))

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                url, params=query, headers=headers, cookies=config.cookies()
            )
    except httpx.HTTPError as error:
        raise EspnError(redact(f"Request to ESPN failed: {error}", config.secrets())) from error

    if response.status_code in (401, 403):
        raise EspnError(
            "ESPN returned "
            f"{response.status_code}. This league is private or the session cookies are "
            "stale. Set ESPN_S2 and ESPN_SWID from a logged-in browser session and restart "
            "the MCP server."
        )
    if response.status_code == 404:
        raise EspnError(
            f"ESPN returned 404 for {response.url.path}. Check the league id and that the "
            f"league existed in season {config.season}."
        )
    if response.status_code >= 400:
        body = redact(response.text[:400], config.secrets())
        raise EspnError(f"ESPN returned {response.status_code}: {body}")

    try:
        payload = response.json()
    except ValueError as error:
        raise EspnError(
            "ESPN returned a non-JSON response, which usually means a login wall."
        ) from error

    # leagueHistory responses arrive as a single element list.
    if isinstance(payload, list) and len(payload) == 1 and "leagueHistory" in url:
        return payload[0]
    return payload
