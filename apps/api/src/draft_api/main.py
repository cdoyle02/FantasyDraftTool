"""HTTP adapter around the pure DVS engine."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
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
