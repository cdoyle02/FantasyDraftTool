# Advanced SoS Tier 2 Phase A — Implementation Plan

> **For agentic workers:** TDD each task; commit after each task passes.

**Goal:** Snap-filtered usage, game-script opportunity adjustment, EPA-allowed QB/RB grid, additive APIs + `WeekSosView` Tier 2 mode.

**Architecture:** New `tier2_*.py` modules; extend `usage.py` with optional snap filter; `service.py` + routes; web client + types.

**Design SSOT:** `docs/superpowers/specs/2026-11-08-advanced-sos-tier2-design.md`

## Global constraints

- Do **not** change Tier 1 / classic default responses
- Coordinate with snapshot usage-rows work in `usage.py` / `snapshot.py` — extend, do not revert
- `k = 4`, buckets 7/18/7 unchanged

## File map

| Path | Responsibility |
|------|----------------|
| `sos/tier2_snap.py` | Parse snap_counts; `(team, week, name_key) → offense_pct` |
| `sos/tier2_epa.py` | EPA allowed per game, shrink, ranks |
| `sos/tier2_game_script.py` | Implied total → delta; adjust softness |
| `sos/tier2.py` | Grid + opportunity rows |
| `sos/usage.py` | `min_snap_pct` + snap index optional args |
| `sos/service.py` | `build_tier2_*` |
| `main.py` | `/tier2`, `/tier2/opportunity` |
| `tests/sos/test_tier2_*.py` | Pure + API |
| `web/WeekSosView.tsx` | Tier 2 view mode |
| `sos/README.md` | Phase A formulas |

---

### Task 1: Snap-filtered usage (pure)

- Test: `test_tier2_usage_snap.py`
- Extend `build_usage_index(..., snap_pct_index=..., min_offense_snap_pct=0.20)`
- Commit: `feat: SoS snap-filtered usage shares`

### Task 2: Game-script adjustment (pure)

- Test: `test_tier2_game_script.py`
- `tier2_game_script.py`
- Commit: `feat: SoS game-script softness adjustment`

### Task 3: EPA allowed + shrink (pure)

- Test: `test_tier2_epa.py`
- `tier2_epa.py`
- Commit: `feat: SoS Tier2 EPA allowed defensive rate`

### Task 4: Tier2 assembly + opportunity

- Test: `test_tier2_opportunity.py`
- `tier2.py`
- Commit: `feat: SoS Tier2 grid and opportunity assembly`

### Task 5: API + service

- Test: `test_api_tier2.py`
- `service.py`, `main.py`
- Commit: `feat: SoS Tier2 HTTP routes`

### Task 6: Web toggle

- `types.ts`, `client.ts`, `WeekSosView.tsx`, `WeekSosView.test.tsx`
- Commit: `feat: WeekSosView Tier2 EPA mode`

### Task 7: README + docs

- `sos/README.md`
- Commit: `docs: SoS Tier2 Phase A formulas`

### Verification

```bash
uv run --package draft-api pytest apps/api/tests/sos -v
pnpm test apps/web/src/week/WeekSosView.test.tsx
```
