"""Request-scoped ESPN logins for the hosted MCP server.

Stdio keeps using the single process environment. The HTTP server sets one
profile per request from the bearer token, and tools read that profile instead
of accepting cookies as arguments.
"""

from __future__ import annotations

import hmac
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass

from .client import EspnConfig, EspnError, load_config

_current: ContextVar[EspnProfile | None] = ContextVar("espn_profile", default=None)


@dataclass(frozen=True)
class EspnProfile:
    name: str
    token: str
    config: EspnConfig


def current_profile() -> EspnProfile | None:
    return _current.get()


def active_config() -> EspnConfig:
    """Cookies for this request, or the process environment when no profile is set."""
    profile = _current.get()
    if profile is not None:
        return profile.config
    return load_config()


def set_profile(profile: EspnProfile) -> Token[EspnProfile | None]:
    return _current.set(profile)


def reset_profile(token: Token[EspnProfile | None]) -> None:
    _current.reset(token)


def _season() -> int:
    raw = os.environ.get("ESPN_SEASON", "").strip()
    try:
        return int(raw) if raw else 2026
    except ValueError as error:
        raise EspnError(f"ESPN_SEASON must be a year, got {raw!r}") from error


def _swid(name: str) -> str | None:
    swid = os.environ.get(name, "").strip() or None
    if swid and not swid.startswith("{"):
        swid = "{" + swid.strip("{}") + "}"
    return swid


def _cookie(name: str) -> str | None:
    return os.environ.get(name, "").strip() or None


def load_http_profiles() -> list[EspnProfile]:
    """Michael is required. Katie is loaded whenever her token is set."""
    season = _season()
    league_id = os.environ.get("ESPN_LEAGUE_ID", "").strip() or None
    michael_token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    if not michael_token:
        raise EspnError("MCP_AUTH_TOKEN must be set for the hosted MCP server.")

    profiles = [
        EspnProfile(
            name="michael",
            token=michael_token,
            config=EspnConfig(
                season=season,
                league_id=league_id,
                espn_s2=_cookie("ESPN_S2"),
                swid=_swid("ESPN_SWID"),
            ),
        )
    ]
    katie_token = os.environ.get("MCP_AUTH_TOKEN_KATIE", "").strip()
    if katie_token:
        profiles.append(
            EspnProfile(
                name="katie",
                token=katie_token,
                config=EspnConfig(
                    season=season,
                    league_id=league_id,
                    espn_s2=_cookie("ESPN_S2_KATIE"),
                    swid=_swid("ESPN_SWID_KATIE"),
                ),
            )
        )
    return profiles


def match_profile(presented: str, profiles: list[EspnProfile]) -> EspnProfile | None:
    """Compare every token so a miss does not reveal which secret was shorter."""
    found: EspnProfile | None = None
    for profile in profiles:
        if not presented or len(presented) != len(profile.token):
            continue
        if hmac.compare_digest(presented, profile.token):
            found = profile
    return found
