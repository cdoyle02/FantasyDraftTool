# Advanced SoS Tier 2 Phase A — Implementation Plan

> **For agentic workers:** TDD each task; commit after each task passes. REQUIRED: design SSOT below.

**Goal:** Snap-filtered usage, Vegas game-script opportunity adjustment, EPA-allowed QB/RB grid, additive APIs + `WeekSosView` Tier 2 mode — without changing Tier 1 / classic defaults.

**Architecture:** New `tier2_*.py` modules; optional snap filter on `build_usage_index`; `service.py` + FastAPI routes; web client + types.

**Tech stack:** Python 3.13, nflverse `stats_player_week` + `snap_counts`, FastAPI, React `WeekSosView`, pytest/vitest.

**Design SSOT:** [2026-11-08-advanced-sos-tier2-design.md](../specs/2026-11-08-advanced-sos-tier2-design.md)

## Global constraints

- Do **not** change Tier 1 / classic default responses or routes
- Coordinate with snapshot `usageStats` work — extend `snapshot.py` / `refresh.py`, do not revert
- Shrink `k = 4`; softness buckets 7 / 18 / 7 unchanged
- Tier 2 grid + opportunity: **QB and RB only** (400 on WR/TE/DST)
- Snap off → Tier-1-style unfiltered usage on Tier 2 opportunity (`snapFiltered: false`)

## File map

| Path | Responsibility |
|------|----------------|
| `sos/tier2_snap.py` | Parse `snap_counts`; `(team, week, name) → offense_pct` |
| `sos/tier2_epa.py` | EPA allowed per game, shrink, ranks |
| `sos/tier2_game_script.py` | Implied total → delta; adjust softness |
| `sos/tier2.py` | Grid + opportunity rows |
| `sos/usage.py` | Optional `snap_pct_index` + `min_offense_snap_pct` |
| `sos/service.py` | `build_tier2_*`, snap/odds resolve |
| `main.py` | `GET …/tier2`, `GET …/tier2/opportunity` |
| `sos/README.md` | Phase A formulas |
| `tests/sos/test_tier2_*.py`, `test_api_tier2.py` | Pure + HTTP |
| `web/WeekSosView.tsx` | Tier 2 view mode (QB/RB) |

---

### Task 0: Snapshot `usageStats` fallback (pre-Tier 2)

**Files:** `snapshot.py`, `nflverse.py`, `refresh.py`, `service.py` (`_resolve_stats_rows`), `data/sos_2026.json`, `test_snapshot.py`, `test_tier1_opportunity_snapshot.py`

- [x] Embed trimmed `usageStats` on refresh; round-trip in snapshot IO
- [x] Tier 1 opportunity falls back to packaged rows when live stats fail

**Verify:** `uv run --package fantasy-draft-api pytest apps/api/tests/sos/test_snapshot.py apps/api/tests/sos/test_tier1_opportunity_snapshot.py -q`

**Commit:** `feat: SoS snapshot usageStats fallback`

---

### Task 1: Snap-filtered usage (pure)

- [x] `test_tier2_usage_snap.py`
- [x] `build_usage_index(..., snap_pct_index=..., min_offense_snap_pct=0.20)`

**Commit:** `feat: SoS snap-filtered usage shares`

---

### Task 2: Game-script adjustment (pure)

- [x] `test_tier2_game_script.py` — `tier2_game_script.py`

**Commit:** `feat: SoS game-script softness adjustment`

---

### Task 3: EPA allowed + shrink (pure)

- [x] `test_tier2_epa.py` — `tier2_epa.py`

**Commit:** `feat: SoS Tier2 EPA allowed defensive rate`

---

### Task 4: Tier 2 assembly + opportunity

- [x] `test_tier2_opportunity.py` — `tier2.py`

**Commit:** `feat: SoS Tier2 grid and opportunity assembly`

---

### Task 5: API + service

- [x] `test_api_tier2.py`, `service.py`, `main.py`

**Commit:** `feat: SoS Tier2 HTTP routes`

---

### Task 6: Web toggle

- [x] `types.ts`, `client.ts`, `WeekSosView.tsx`, `WeekSosView.test.tsx`

**Commit:** `feat: WeekSosView Tier2 EPA mode`

---

### Task 7: Docs

- [x] `sos/README.md`, design plan (this file)

**Commit:** `docs: SoS Tier2 Phase A plan and formulas`

---

## Verification (Definition of done)

```bash
uv run --package fantasy-draft-api pytest apps/api/tests/sos -q
pnpm test -- WeekSosView
```

Expected: all SoS tests green; Tier 1 regressions unchanged; web smoke includes Tier 2 fetch URLs.

## Remaining unknowns / follow-ups

- Packaged snapshot does **not** embed snap_counts (live fetch only); offline Tier 2 opportunity uses unfiltered usage unless snap override in tests
- EPA columns rely on live `stats_player_week` (or packaged `usageStats` trim set — EPA fields present only when refresh included them)
- WR/TE Tier 2 splits deferred to Phase B per design
