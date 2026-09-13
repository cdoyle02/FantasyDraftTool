"""HTTP adapter around the pure DVS engine."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from dvs_engine import (
    CsvImportError,
    adjustment_from_dict,
    as_jsonable,
    import_players_csv,
    recommend,
)
from dvs_engine import __version__ as engine_version
from dvs_engine.models import player_from_dict, settings_from_dict, state_from_dict
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import RequestResponseEndpoint

from . import __version__
from .espn_available_dst import (
    EspnAvailableError,
    espn_credentials_from_env,
    fetch_available_dst,
    fetch_available_k,
)
from .espn_leagues import LeagueNotFoundError, get_league, leagues_payload
from .implied_totals import GameLine
from .jared_k import JaredKError, fetch_jared_k_rankings
from .jared_k_available import build_jared_available_payload
from .kyle_dst import KyleDstError, fetch_kyle_dst_rankings
from .kyle_dst_available import build_kyle_available_payload
from .odds import OddsApiError, OddsProvider, TheOddsApiProvider, TtlCache
from .week_odds import build_week_odds_payload


class ApiModel(BaseModel):
    model_config = {"populate_by_name": True}


class PlayerPayload(ApiModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    position: Literal["QB", "RB", "WR", "TE", "K", "DST"]
    team: str = ""
    projected_points: float = Field(alias="projectedPoints")
    adp: float | None = Field(default=None, gt=0)
    tier: int = Field(default=1, ge=1)
    depth_chart_rank: int | None = Field(default=None, alias="depthChartRank", ge=1)
    depth_chart_source: str | None = Field(default=None, alias="depthChartSource")
    upside_score: float | None = Field(default=None, alias="upsideScore")
    risk_score: float | None = Field(default=None, alias="riskScore")
    is_rookie: bool = Field(default=False, alias="isRookie")
    is_breakout: bool = Field(default=False, alias="isBreakout")
    injury_status: str | None = Field(default=None, alias="injuryStatus")
    ir_eligible: bool = Field(default=False, alias="irEligible")
    expected_return_week: int | None = Field(default=None, alias="expectedReturnWeek", ge=1)
    bye_week: int | None = Field(default=None, alias="byeWeek", ge=1, le=18)


class AdjustmentPayload(ApiModel):
    player_id: str = Field(alias="playerId", min_length=1)
    points_delta: float = Field(default=0, alias="pointsDelta")
    tier_override: int | None = Field(default=None, alias="tierOverride", ge=1)
    tag: Literal["myGuy", "avoid", "irStash"] | None = None
    note: str = ""


class LeagueSettingsPayload(ApiModel):
    team_count: int = Field(default=12, alias="teamCount", ge=2, le=32)
    roster_slots: dict[str, int] = Field(
        default_factory=lambda: {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "SUPERFLEX": 0,
            "BENCH": 6,
            "K": 1,
            "DST": 1,
        },
        alias="rosterSlots",
    )
    scoring_format: Literal["PPR", "halfPPR", "standard"] = Field(
        default="PPR", alias="scoringFormat"
    )
    draft_type: Literal["snake"] = Field(default="snake", alias="draftType")
    league_type: str = Field(default="redraft", alias="leagueType")
    user_team_id: str = Field(default="1", alias="userTeamId")
    keeper_slots: int = Field(default=0, alias="keeperSlots", ge=0)
    ir_slots: int = Field(default=0, alias="irSlots", ge=0)
    formula_version: int | None = Field(default=None, alias="formulaVersion", ge=1, le=5)
    formula_params: dict[str, Any] | None = Field(default=None, alias="formulaParams")


class PickPayload(ApiModel):
    event_id: str = Field(default="", alias="eventId")
    pick_number: int = Field(alias="pickNumber", ge=1)
    team_id: str = Field(alias="teamId", min_length=1)
    player_id: str = Field(alias="playerId", min_length=1)
    timestamp: str = ""


class DraftStatePayload(ApiModel):
    team_count: int = Field(default=12, alias="teamCount", ge=2, le=32)
    pick_history: list[PickPayload] = Field(default_factory=list, alias="pickHistory")
    reserved_rosters: dict[str, list[str]] = Field(default_factory=dict, alias="reservedRosters")


class RecommendationRequest(ApiModel):
    players: list[PlayerPayload]
    settings: LeagueSettingsPayload = Field(default_factory=LeagueSettingsPayload)
    draft_state: DraftStatePayload | None = Field(default=None, alias="draftState")
    adjustments: list[AdjustmentPayload] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=500)


class CsvImportRequest(ApiModel):
    content: str = Field(min_length=1)
    column_mapping: dict[str, str] = Field(default_factory=dict, alias="columnMapping")
    strict: bool = True

app = FastAPI(title="Fantasy Draft Tool API", version=__version__)
logging.basicConfig(
    level=os.getenv("FANTASY_DRAFT_LOG_LEVEL", "INFO").upper(),
    format="%(message)s",
)
logger = logging.getLogger("fantasy_draft_api")
origins = [
    origin.strip()
    for origin in os.getenv(
        "FANTASY_DRAFT_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Odds provider is injectable for tests; production uses The Odds API + TTL cache.
_odds_provider_override: OddsProvider | None = None
_odds_cache: TtlCache[list[GameLine]] = TtlCache(
    ttl_seconds=float(os.getenv("ODDS_CACHE_TTL_SECONDS", "1800"))
)

# Kyle DST scrape cache (HTML is slower / more fragile than odds).
_kyle_dst_cache: TtlCache[dict[str, Any]] = TtlCache(
    ttl_seconds=float(os.getenv("KYLE_DST_CACHE_TTL_SECONDS", "1800"))
)
_kyle_dst_http_get_override: Any | None = None
_espn_available_http_json_override: Any | None = None

# Jared Smola weekly K scrape cache.
_jared_k_cache: TtlCache[dict[str, Any]] = TtlCache(
    ttl_seconds=float(os.getenv("JARED_K_CACHE_TTL_SECONDS", "1800"))
)
_jared_k_http_get_override: Any | None = None


def set_kyle_dst_http_get(http_get: Any | None) -> None:
    """Test hook: override FantasyPros HTML fetcher (None restores default)."""
    global _kyle_dst_http_get_override
    _kyle_dst_http_get_override = http_get
    _kyle_dst_cache.clear()


def set_jared_k_http_get(http_get: Any | None) -> None:
    """Test hook: override Jared FantasyPros HTML fetcher (None restores default)."""
    global _jared_k_http_get_override
    _jared_k_http_get_override = http_get
    _jared_k_cache.clear()


def set_espn_available_http_json(http_json: Any | None) -> None:
    """Test hook: override ESPN JSON fetcher (None restores default)."""
    global _espn_available_http_json_override
    _espn_available_http_json_override = http_json


def get_kyle_dst_rankings_cached(*, week: int | None = None) -> dict[str, Any]:
    # Cache key is week-agnostic for “current” requests; explicit week skips shared cache.
    if week is None:
        cached = _kyle_dst_cache.get()
        if cached is not None:
            return cached
    payload = fetch_kyle_dst_rankings(week=week, http_get=_kyle_dst_http_get_override)
    if week is None:
        _kyle_dst_cache.set(payload)
    return payload


def get_jared_k_rankings_cached(*, week: int | None = None) -> dict[str, Any]:
    if week is None:
        cached = _jared_k_cache.get()
        if cached is not None:
            return cached
    payload = fetch_jared_k_rankings(week=week, http_get=_jared_k_http_get_override)
    if week is None:
        _jared_k_cache.set(payload)
    return payload


class _CachingOddsProvider:
    """Wraps an OddsProvider with process-local TTL caching."""

    def __init__(self, inner: OddsProvider, cache: TtlCache[list[GameLine]]) -> None:
        self._inner = inner
        self._cache = cache

    def fetch_nfl_odds(self) -> list[GameLine]:
        cached = self._cache.get()
        if cached is not None:
            return cached
        games = self._inner.fetch_nfl_odds()
        self._cache.set(games)
        return games


def set_odds_provider(provider: OddsProvider | None) -> None:
    """Test hook: override the odds provider (None restores env-based default)."""
    global _odds_provider_override
    _odds_provider_override = provider
    _odds_cache.clear()


def get_odds_provider() -> OddsProvider:
    if _odds_provider_override is not None:
        return _odds_provider_override
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        raise OddsApiError(
            "ODDS_API_KEY is not set. Add it to your environment (see .env.example)."
        )
    return _CachingOddsProvider(TheOddsApiProvider(api_key), _odds_cache)


@app.middleware("http")
async def request_log(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            separators=(",", ":"),
        )
    )
    return response


def error_response(
    status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request
    return error_response(
        422, "request_validation_error", "Request validation failed", exc.errors()
    )


@app.exception_handler(CsvImportError)
async def csv_import_error_handler(request: Request, exc: CsvImportError) -> JSONResponse:
    del request
    return error_response(
        422,
        "csv_import_error",
        str(exc),
        [as_jsonable(issue) for issue in exc.issues],
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    del request
    return error_response(400, "domain_validation_error", str(exc))


@app.get("/health")
@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/version")
def version() -> dict[str, str]:
    return {"api": __version__, "engine": engine_version}


@app.post("/api/v1/recommendations")
def recommendations(request: RecommendationRequest) -> dict[str, Any]:
    settings = settings_from_dict(request.settings.model_dump(by_alias=True))
    state_payload = (
        request.draft_state.model_dump(by_alias=True)
        if request.draft_state is not None
        else {"teamCount": settings.team_count}
    )
    state = state_from_dict(state_payload, settings.team_count)
    players = [player_from_dict(item.model_dump(by_alias=True)) for item in request.players]
    adjustments = {
        adjustment.player_id: adjustment
        for adjustment in (
            adjustment_from_dict(item.model_dump(by_alias=True))
            for item in request.adjustments
        )
    }
    results = recommend(players, state, settings, adjustments, request.limit)
    return {
        "recommendations": as_jsonable(results),
        "count": len(results),
        "configuration": {
            "formulaVersion": settings.formula_params.formula_version,
            "oneTurnSims": settings.formula_params.one_turn_sims,
            "simulationSeed": settings.formula_params.sim_seed,
            "formulaParams": as_jsonable(settings.formula_params),
        },
    }


@app.post("/api/v1/imports/csv")
def csv_import(request: CsvImportRequest) -> dict[str, Any]:
    result = import_players_csv(
        request.content, request.column_mapping, strict=request.strict
    )
    return {
        "players": as_jsonable(result.players),
        "warnings": as_jsonable(result.warnings),
        "adjustments": [],
    }


@app.get("/api/v1/nfl/week-odds", response_model=None)
def week_odds() -> dict[str, Any] | JSONResponse:
    """Current fantasy-week NFL spreads/totals with ranked favorite D/ST plays."""
    try:
        provider = get_odds_provider()
        return build_week_odds_payload(provider, now=datetime.now(timezone.utc))
    except (OddsApiError, ValueError) as exc:
        # OddsApiError: provider/key failures. ValueError: bad NFL_SEASON_WEEK1_TUESDAY.
        return error_response(503, "odds_unavailable", str(exc))


@app.get("/api/v1/espn/leagues", response_model=None)
def espn_leagues() -> dict[str, Any]:
    """Committed ESPN league directory for the Week D/ST picker."""
    return leagues_payload()


@app.get("/api/v1/nfl/kyle-dst-rankings", response_model=None)
def kyle_dst_rankings() -> dict[str, Any] | JSONResponse:
    """Kyle Krajewski weekly DST rankings scraped from FantasyPros."""
    try:
        return get_kyle_dst_rankings_cached()
    except KyleDstError as exc:
        return error_response(503, "kyle_rankings_unavailable", str(exc))


@app.get("/api/v1/nfl/kyle-dst-available", response_model=None)
def kyle_dst_available(leagueId: str) -> dict[str, Any] | JSONResponse:
    """Kyle DST rankings plus FREEAGENT/WAIVERS defenses for a configured league."""
    try:
        league = get_league(leagueId)
    except LeagueNotFoundError as exc:
        return error_response(404, "league_not_found", str(exc))

    try:
        rankings_payload = get_kyle_dst_rankings_cached()
    except KyleDstError as exc:
        return error_response(503, "kyle_rankings_unavailable", str(exc))

    try:
        espn_s2, swid, season = espn_credentials_from_env()
        available = fetch_available_dst(
            league_id=league["id"],
            season=season,
            espn_s2=espn_s2,
            swid=swid,
            http_json=_espn_available_http_json_override,
        )
    except EspnAvailableError as exc:
        return error_response(503, "espn_unavailable", str(exc))

    return build_kyle_available_payload(
        rankings_payload=rankings_payload,
        available=available,
        league=league,
    )


@app.get("/api/v1/nfl/jared-k-rankings", response_model=None)
def jared_k_rankings() -> dict[str, Any] | JSONResponse:
    """Jared Smola weekly K rankings scraped from FantasyPros."""
    try:
        return get_jared_k_rankings_cached()
    except JaredKError as exc:
        return error_response(503, "jared_rankings_unavailable", str(exc))


@app.get("/api/v1/nfl/jared-k-available", response_model=None)
def jared_k_available(leagueId: str) -> dict[str, Any] | JSONResponse:
    """Jared K rankings plus FREEAGENT/WAIVERS kickers for a configured league."""
    try:
        league = get_league(leagueId)
    except LeagueNotFoundError as exc:
        return error_response(404, "league_not_found", str(exc))

    try:
        rankings_payload = get_jared_k_rankings_cached()
    except JaredKError as exc:
        return error_response(503, "jared_rankings_unavailable", str(exc))

    try:
        espn_s2, swid, season = espn_credentials_from_env()
        available = fetch_available_k(
            league_id=league["id"],
            season=season,
            espn_s2=espn_s2,
            swid=swid,
            http_json=_espn_available_http_json_override,
        )
    except EspnAvailableError as exc:
        return error_response(503, "espn_unavailable", str(exc))

    return build_jared_available_payload(
        rankings_payload=rankings_payload,
        available=available,
        league=league,
    )
