# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A platform-independent, local-first fantasy football draft assistant (works alongside ESPN, Sleeper, Yahoo — not dependent on any of them). Its core IP is the Draft Value Score (DVS) formula: a pure, dependency-free engine that blends replacement value (VORP), tier-cliff urgency, roster marginal value / wait-loss, and configurable guardrails into explainable live pick recommendations. See `PROJECT_SPEC.md` for full product rationale and phased roadmap — note the actual architecture (Python engine + FastAPI + Pyodide) superseded that doc's original all-TypeScript proposal.

## Repository layout

- `apps/web` — React/TypeScript PWA: draft board, Dexie (IndexedDB) persistence, offline engine adapter.
- `apps/api` — stateless FastAPI adapter (`draft_api`). Validates HTTP requests and calls the engine; contains no scoring rules itself.
- `packages/dvs-engine` — dependency-free Python domain package (`dvs_engine`). The DVS formula lives here and nowhere else.
- `tools/espn-mcp` — dev-time MCP server for exploring ESPN's undocumented fantasy v3 API while building ESPN draft integration. Not a runtime dependency; has its own `uv` project.
- `docs/` — `architecture.md`, `formula.md` (DVS component assumptions), `offline-readiness.md` (pre-draft device checklist), `deployment.md`.

## Commands

Install once:
```bash
pnpm install
uv sync --all-packages --all-groups
```

Run locally (two terminals):
```bash
pnpm api:dev   # FastAPI on :8000
pnpm dev       # Vite dev server on :5173
```
`VITE_API_BASE_URL` (in `apps/web/.env.local`) points the web client at the API; `.env.example` at repo root lists the API's own env vars (`FANTASY_DRAFT_CORS_ORIGINS`, `FANTASY_DRAFT_LOG_LEVEL`).

Checks (what CI runs, in `.github/workflows/ci.yml`):
```bash
uv run ruff check .
uv run mypy packages/dvs-engine/src apps/api/src
uv run pytest
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

Single-test / scoped runs:
```bash
uv run pytest packages/dvs-engine/tests/test_formula_v2.py -k wait_loss
uv run pytest apps/api/tests/test_api.py
pnpm --filter @fantasy-draft-tool/web test -- src/store/draftStore.test.ts
pnpm --filter @fantasy-draft-tool/web exec vitest run -t "some test name"
```

Other useful scripts (root `package.json`):
- `pnpm build:engine` — builds the `dvs-engine` wheel into `apps/web/public/engine` (required before the offline Pyodide path or `test:e2e` will work).
- `pnpm generate:api` — regenerates `apps/web/src/api/schema.generated.ts` from the FastAPI OpenAPI schema.

Python tooling is `uv`-based workspace-wide (root `pyproject.toml` lists `apps/api` and `packages/dvs-engine` as members; `tools/espn-mcp` is excluded and has its own lockfile). Ruff line-length 100, targets py313; mypy runs in `strict` mode on `packages/dvs-engine/src` and `apps/api/src`.

## Architecture

**Local-first, dual-runtime engine.** `packages/dvs-engine` is plain-dataclass Python with zero dependencies and no I/O, so the identical package runs both in CPython (via FastAPI) and in the browser (via Pyodide in a Web Worker). `apps/web/src/engine/adapter.ts` picks the runtime at request time:
1. If `navigator.onLine`, try the FastAPI `/api/v1/recommendations` endpoint.
2. On failure or offline, fall back to the Pyodide worker (`apps/web/src/workers/dvs.worker.ts`), which calls `dvs_engine.browser.recommendation_json` (a string-in/string-out entrypoint that avoids Python↔JS object bridging).
3. If the Python engine itself isn't ready yet, fall back to a non-production TypeScript scorer (`apps/web/src/engine/fallback.ts`) and surface a warning — this path must never be mistaken for the real engine's output.

Golden fixtures should be checked against both runtimes to catch behavior drift between CPython and Pyodide.

**Event-sourced draft state.** Picks are immutable events with stable IDs; the board and rosters are derived from the ordered event stream (`apps/web/src/data/db.ts` — Dexie tables `players`, `picks`, `settings`, `adjustments`, `events`). Corrections append/replace events rather than mutating history in place, and undo removes the most recent local event (`draftStore.ts`: `draftPlayer`, `correctPick`, `undoLastPick`, `removePick` each `db.*.put`/`queueEvent` then re-derive). This shape is intentionally reused for later cloud sync and Sleeper ingestion — don't introduce a second state representation.

**Imported data vs. user opinion are separate layers.** Baseline projections/ADP/tier come from CSV import; boosts, fades, tier overrides, and `myGuy`/`avoid` tags live in a separate `UserAdjustment` layer keyed by player ID (Dexie `adjustments` table server-side `UserAdjustment` dataclass). `effective_player()` in `formula.py` merges them at scoring time without mutating imported data — re-importing a new baseline must never erase user opinions.

**DVS formula versions coexist.** `FormulaParams.formula_version` (currently 2, see `packages/dvs-engine/src/dvs_engine/models.py`) selects between `_recommend_v1` and `_recommend_v2` in `formula.py`:
- v1: `VORP × need × demand + tier-urgency + guardrails + tag bonus`.
- v2 (current default): replaces the VORP/need multiplier with roster **marginal value** (`lineup.py::marginal_value` — the point gain from actually inserting this player into the user's roster/bench, with position-depth bench discounting) plus **wait-loss** (`formula.py::wait_loss` — expected value lost by not drafting now, computed from the survival-weighted value of the best same-position fallback at the next turn).
- Both versions still run guardrails (soft QB/TE/K/DST suppression, RB/WR balance bands — `guardrail_adjustment`) and label results `CAN'T PASS` / `BEST PICK` / `SAFE TO WAIT`, but the label thresholds differ per version (VORP+survival for v1; marginal-value+wait-loss for v2).
- Opponent demand (`opponent_demand_factor`) is currently a neutral no-op (`demand = 1.0` in both versions) — Phase 1.5 in `PROJECT_SPEC.md`. Don't write reasons/copy implying opponent behavior is predicted until it's wired in.

**Field naming crosses a language boundary deliberately.** TypeScript uses camelCase (`Player`, `LeagueSettings`, `Recommendation` in `apps/web/src/types.ts`); the wire format and Python side use a mix (Pydantic payloads in `apps/api/src/draft_api/main.py` accept camelCase aliases via `Field(alias=...)`, dataclasses in `dvs_engine/models.py` are snake_case with dict-conversion helpers like `player_from_dict`/`settings_from_dict` that accept either casing). `apps/web/src/api/client.ts` (`serializeRecommendationRequest`/`normalizeRecommendations`) is the single translation point on the frontend — extend it rather than leaking wire-format field names into components or the store.

**Offline PWA readiness** depends on `pnpm build:engine` having produced a wheel under `apps/web/public/engine` and on the Vite PWA workbox config (`apps/web/vite.config.ts`) caching that wheel plus the Pyodide CDN runtime. `docs/offline-readiness.md` is the manual pre-draft device checklist; treat it as required reading before shipping anything touching the worker, service worker, or caching config.

## Deployment

Web (Cloudflare Pages) needs `VITE_API_BASE_URL` set at build time and must not strip the service worker/wheel/Pyodide assets from `dist`. API (Railway, `railway.toml` → `apps/api/Dockerfile`) needs `FANTASY_DRAFT_CORS_ORIGINS` and `FANTASY_DRAFT_LOG_LEVEL`, and should stay warm during live drafts if the host sleeps idle services. See `docs/deployment.md` for the full release checklist (tests → build → Playwright offline scenario → manual offline-readiness pass against the deployed app).
