# Draft-ready feature slices

## Goal

Make the app safe to rehearse and use during a live draft, then improve recommendation clarity without changing DVS ranking behavior.

## Guardrails

- Complete one batch at a time and stop for review after each green batch.
- Add exactly three unit tests per batch: happy path, boundary, and failure mode.
- Preserve manual pick entry as the fallback in every mode.
- Keep pick sources separate from core player and engine models so future providers remain possible.

## Sequence

### 1. Draft-safe scoring and green CI

- Fix the existing Ruff, mypy, engine-version, and E2E package-filter failures in [ci.yml](../../.github/workflows/ci.yml), [csv_import.py](../../packages/dvs-engine/src/dvs_engine/csv_import.py), and engine metadata/tests.
- Update [adapter.ts](../../apps/web/src/engine/adapter.ts) so production never silently uses the development scorer; expose an actionable unavailable-engine state while preserving manual draft state.
- Align the offline wheel version and build references in [dvs.worker.ts](../../apps/web/src/workers/dvs.worker.ts) and package metadata.
- **Local offline-engine runtime packaging:** bundle and serve the Pyodide browser runtime locally; direct the module worker away from CDN loading; retain an appropriate first-load readiness strategy; and verify the live browser reaches Offline Ready. Keep this separate from the ESPN MCP smoke test.
- Tests: API success, Pyodide recovery, and both engines unavailable in production.

### 2. Replay/mock mode

- Introduce a source-neutral normalized-pick contract and replay source near [draftStore.ts](../../apps/web/src/store/draftStore.ts), keeping source IDs outside the core engine.
- Add minimal start, pause/advance, and reset controls; replay ESPN-shaped fixtures through the real Dexie/Zustand/recommendation path.
- Use two reviewable batches if needed: replay ingestion first, controls second, each with exactly three tests.

### 3. One-click ESPN refresh

- Port only the proven public `mDraftDetail` read path from [tools/espn-mcp](../../tools/espn-mcp) into a thin FastAPI endpoint in [main.py](../../apps/api/src/draft_api/main.py).
- Add player normalization/matching, ESPN-team-to-snake-seat mapping, and append-only reconciliation before picks reach [draftStore.ts](../../apps/web/src/store/draftStore.ts).
- Add league ID, refresh action, status, and unmatched-player fallback to the web UI.
- Keep continuous polling, private cookies, auctions, and generic ESPN lobby guarantees out of this slice.
- Implement as three small batches: API fetch/normalize, match/reconcile, then UI refresh; each gets exactly three tests.

### 4. Clearer DVS v2 explanations

- Update recommendation cards in [App.tsx](../../apps/web/src/App.tsx) to emphasize `marginalValue` and `waitLoss`, and remove misleading need-multiplier emphasis for v2.
- Preserve formula output and ranking order; this is explanation-only.
- Tests: complete v2 breakdown, zero/edge values, and missing/degraded breakdown handling.

## Batches

1. Restore green CI, align offline engine packaging, and make production scoring fail closed.
2. Add the normalized pick-source contract and replay ingestion.
3. Add minimal replay controls and reset behavior.
4. Add the public ESPN draft-picks API proxy and normalization.
5. Add ESPN player/team matching and append-only pick reconciliation.
6. Add one-click ESPN refresh, status, and manual fallback UI.
7. Show accurate DVS v2 marginal-value and wait-loss explanations.

Each batch adds exactly three focused unit tests and stops for review after all relevant checks pass.

## Verification

For every batch, run its focused tests first, then the relevant full suite. Before closing the fourth feature, run:

- `uv run ruff check .`
- `uv run mypy packages/dvs-engine/src apps/api/src`
- `uv run pytest`
- `pnpm lint`
- `pnpm test`
- `pnpm build`
- `pnpm test:e2e`

## Deferred until reassessment

Continuous ESPN polling, private-league authentication, generic ESPN mock-lobby integration, opponent-demand/formula tuning, accounts, cloud sync, auction drafts, and keepers.
