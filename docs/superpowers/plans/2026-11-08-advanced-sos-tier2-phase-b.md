# Advanced SoS Tier 2 Phase B — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or execute task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Package snap counts + EPA columns for Railway/offline Tier 2; extend EPA grid and opportunity to WR/TE.

**Architecture:** Extend Phase A modules (`tier2_snap`, `tier2_epa`, `snapshot`, `usage`, `service`, `WeekSosView`) — no new top-level package.

**Tech Stack:** Python 3.13, nflverse snap_counts + stats_player_week, FastAPI, React, pytest/vitest.

## Global Constraints

- Design SSOT: `docs/superpowers/specs/2026-11-08-advanced-sos-tier2-phase-b-design.md`
- Do **not** break Tier 1 or Phase A QB/RB behavior
- Do **not** implement Clay Out/Slot SoS splits in this phase
- Prefer TDD; commit frequently; never commit secrets

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/sos/usage.py` | Add EPA fields to `USAGE_STATS_FIELDS` |
| `apps/api/src/draft_api/sos/snapshot.py` | Round-trip `snapCounts` |
| `apps/api/src/draft_api/sos/nflverse.py` | `SosDataset.snap_counts` field; load on refresh |
| `apps/api/src/draft_api/sos/refresh.py` | Fetch + embed snap counts |
| `apps/api/src/draft_api/sos/tier2_snap.py` | Trim helpers for packaging |
| `apps/api/src/draft_api/sos/tier2_epa.py` | WR/TE `receiving_epa` aggregation |
| `apps/api/src/draft_api/sos/service.py` | Snap fallback chain; allow WR/TE on tier2 |
| `apps/api/src/draft_api/sos/README.md` | Phase B notes |
| `apps/api/src/draft_api/data/sos_2026.json` | Regenerated with snaps + EPA fields |
| `apps/api/tests/sos/test_tier2_*.py`, `test_snapshot.py` | Coverage |
| `apps/web/src/week/WeekSosView.tsx` | Tier 2 for WR/TE |

---

### Task 1: EPA columns in usageStats trim

**Files:** `usage.py`, `test_tier1_usage.py` / snapshot tests

- [ ] Add `passing_epa`, `rushing_epa`, `receiving_epa` to `USAGE_STATS_FIELDS`
- [ ] Test trimmed row keeps receiving_epa when present
- [ ] Commit `feat: include EPA columns in SoS usageStats trim`

---

### Task 2: Package snapCounts in sos snapshot

**Files:** `tier2_snap.py`, `snapshot.py`, `nflverse.py`, `refresh.py`, `service.py`, tests

**Interfaces:**
- `trim_snap_counts_row(row) -> dict`
- `SosDataset.snap_counts: tuple[dict, ...]`
- Snapshot key `snapCounts`
- `_resolve_snap_rows(season, dataset) -> (rows, from_snapshot)` — live then packaged

- [ ] TDD round-trip + opportunity `snapFiltered: true` when only packaged snaps exist
- [ ] Commit `feat: package snapCounts in SoS snapshot for offline Tier 2`

---

### Task 3: WR/TE EPA-allowed grid + opportunity

**Files:** `tier2_epa.py`, `tier2.py`, `service.py`, `main.py` validation, tests

- [ ] `defensive_epa_allowed_per_game` for WR/TE uses `receiving_epa`
- [ ] Allow `position in {QB,RB,WR,TE}` on tier2 builders (DST still ValueError/400)
- [ ] Commit `feat: SoS Tier2 EPA grid for WR and TE`

---

### Task 4: WeekSosView Tier 2 for WR/TE

**Files:** `WeekSosView.tsx`, `WeekSosView.test.tsx`

- [ ] Remove auto-fallback to Tier 1 for WR/TE when Tier 2 selected
- [ ] Keep DST on classic/Tier 1 only
- [ ] Commit `feat: enable SoS Tier 2 mode for WR and TE`

---

### Task 5: Refresh snapshot + verify

- [ ] `uv run --project apps/api python -m draft_api.sos.refresh --season 2026`
- [ ] Assert `usageStats` has EPA keys and `snapCounts` non-empty
- [ ] `pytest apps/api/tests/sos -q` + `pnpm test -- WeekSosView`
- [ ] Commit snapshot + push branch

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Packaged snapCounts | 2, 5 |
| EPA in usageStats | 1, 5 |
| WR/TE Tier 2 | 3, 4 |
| Tier 1 unchanged | all |
