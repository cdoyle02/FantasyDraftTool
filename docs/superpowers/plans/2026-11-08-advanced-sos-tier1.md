# Advanced SoS Tier 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Tier 1 advanced SoS in `draft_api/sos/`: L8-default rolling shrunk aFPA, L4/L8/season window toggle, top-7/mid/bottom-7 softness buckets, opportunity = softness × usage share, ESPN roster join, offline backtest harness, and web SoS UI upgrades.

**Architecture:** Pure functions in `calculate.py` + new `usage.py` / `tier1.py`; service layer extends existing `build_sos_payload` path without breaking FPA/PAE; optional opportunity endpoint uses P1-style ESPN fetch. Mirror workbook TTL/snapshot patterns.

**Tech Stack:** Python 3.13, nflverse `stats_player_week`, FastAPI, React `WeekSosView`, pytest/vitest.

## Global Constraints

- Design SSOT: `docs/superpowers/specs/2026-11-08-advanced-sos-tier1-design.md`
- Do **not** remove or change default behavior of existing `GET /strength-of-schedule` FPA/PAE until UI explicitly switches (additive Tier 1 routes)
- Shrinkage `k=4` unless spec amended
- DST: unchanged in Tier 1 opportunity path
- Share identity helpers with `draft_api/workbook/identity.py` (import, no duplication)
- Never commit secrets; roster join uses env ESPN cookies
- Workbook cross-link from SoS UI should use sessionStorage keys from P1 plan when available

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/sos/calculate.py` | `shrink_afpa`, `softness_from_rank`, bucket constants |
| `apps/api/src/draft_api/sos/usage.py` | `usage_share_by_player` from stats rows |
| `apps/api/src/draft_api/sos/tier1.py` | Assemble tier1 team grid + player opportunity rows |
| `apps/api/src/draft_api/sos/roster_join.py` | ESPN roster + `PlayerRef` join |
| `apps/api/src/draft_api/sos/service.py` | `build_tier1_response`, `build_tier1_opportunity_response` |
| `apps/api/src/draft_api/sos/README.md` | Formulas, k, buckets, opportunity |
| `apps/api/src/draft_api/main.py` | Two new GET routes |
| `apps/api/tests/sos/test_tier1_shrink.py` | Pure shrink + buckets |
| `apps/api/tests/sos/test_tier1_usage.py` | Share denominators |
| `apps/api/tests/sos/test_tier1_opportunity.py` | End-to-end fixture |
| `apps/api/tests/sos/test_api_tier1.py` | TestClient |
| `apps/api/tests/sos/fixtures/tier1_backtest_summary.json` | Committed backtest output |
| `apps/api/tests/sos/test_tier1_backtest.py` | Offline Spearman harness |
| `apps/web/src/week/types.ts` | Tier1 types |
| `apps/web/src/api/client.ts` | `strengthOfScheduleTier1`, `tier1Opportunity` |
| `apps/web/src/week/WeekSosView.tsx` | L4/L8/season toggle, tier1 mode, opportunity panel |
| `apps/web/src/week/WeekSosView.test.tsx` | Window + tier1 smoke |

---

### Task 1: Shrunk aFPA + softness buckets (pure)

**Files:**
- Modify: `apps/api/src/draft_api/sos/calculate.py`
- Test: `apps/api/tests/sos/test_tier1_shrink.py`

**Interfaces:**
- Produces:
  - `SHRINK_K = 4`
  - `def shrink_afpa(raw: float | None, prior: float, n: int, k: int = SHRINK_K) -> float | None`
  - `Softness = Literal["soft","neutral","tough"]`
  - `def rank_defenses_shrunk(afpa_by_team: dict[str, float | None]) -> dict[str, int]`  # 1 = softest
  - `def softness_bucket(rank: int) -> tuple[Softness, float]`  # bucket + score 0/0.5/1.0
  - `def resolve_sos_window(mode: Literal["l4","l8","season"], rated_through_week: int) -> set[int]`

- [ ] **Step 1: Tests** — n=0 → prior; rank 7 soft, 8 neutral, 26 neutral, 27 tough; L8 week set size

- [ ] **Step 2: Run** `uv run --package draft-api pytest apps/api/tests/sos/test_tier1_shrink.py -v` → FAIL

- [ ] **Step 3: Implement**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: SoS Tier1 shrunk aFPA and softness buckets`

---

### Task 2: Usage shares from nflverse stats

**Files:**
- Create: `apps/api/src/draft_api/sos/usage.py`
- Test: `apps/api/tests/sos/test_tier1_usage.py`
- Reuse: stats parsing from `sos/nflverse.py` where possible

**Interfaces:**
- Produces:
  - `@dataclass class PlayerUsage: gsis_id: str | None; player_name: str; team: str; position: Position; usage_share: float | None`
  - `build_usage_index(stats_rows: list[dict], *, position: Position, weeks: set[int]) -> list[PlayerUsage]`
  - Team denominators summed only within window; bye weeks excluded

- [ ] **Step 1–4: TDD** fixture stats CSV snippet (2 RBs same team)

- [ ] **Step 5: Commit** `feat: SoS Tier1 player usage shares`

---

### Task 3: Tier1 payload builder

**Files:**
- Create: `apps/api/src/draft_api/sos/tier1.py`
- Test: extend `test_tier1_shrink.py` or new `test_tier1_payload.py`

**Interfaces:**
- Consumes: `SosDataset`, window mode, `position`, `week` (for schedule slice)
- Produces:
  - `build_tier1_grid(dataset, *, position, window, start_week, end_week) -> dict`  
    - Each cell: `shrunkAfpa`, `rank`, `softness`, `softnessScore`, `opponent`
  - `build_player_opportunity(dataset, usage_index, grid, *, week) -> list[dict]`  
    - Match upcoming opponent defense for player's team in `week`

- [ ] **Step 1–4: TDD** with `SosDataset` fixture from existing tests

- [ ] **Step 5: Commit** `feat: assemble SoS Tier1 grid and opportunity rows`

---

### Task 4: ESPN roster join

**Files:**
- Create: `apps/api/src/draft_api/sos/roster_join.py`
- Reuse: `espn_roster.py` from P1 when landed; until then duplicate minimal fetch or import from workbook module
- Test: `apps/api/tests/sos/test_tier1_opportunity.py`

**Interfaces:**
- `join_roster_opportunity(roster: list[EspnRosterPlayer], opportunities: list[PlayerUsage], grid, *, position) -> list[dict]`
- Uses `workbook.identity.normalize_player_name` + `normalize_team`

- [ ] **Step 1–4: TDD** fixture roster JSON

- [ ] **Step 5: Commit** `feat: ESPN roster join for SoS Tier1 opportunity`

---

### Task 5: Service + API routes

**Files:**
- Modify: `apps/api/src/draft_api/sos/service.py`
- Modify: `apps/api/src/draft_api/main.py`
- Test: `apps/api/tests/sos/test_api_tier1.py`

**Interfaces:**
- `GET /api/v1/nfl/strength-of-schedule/tier1?position=&window=l4|l8|season&startWeek=&endWeek=&season=`
- `GET /api/v1/nfl/strength-of-schedule/tier1/opportunity?position=&window=&week=&leagueId=`
- Default `window=l8` when param omitted
- Response includes `ratedThroughWeek`, `shrinkK`, `stale`, `source`

- [ ] **Step 1: TestClient** with `set_sos_dataset_override`

- [ ] **Step 2–4: Wire**

- [ ] **Step 5: Commit** `feat: SoS Tier1 API routes`

---

### Task 6: Backtest harness (offline)

**Files:**
- Create: `apps/api/tests/sos/test_tier1_backtest.py`
- Create: `apps/api/tests/sos/fixtures/tier1_games_mini.json` (if needed)
- Output: `apps/api/tests/sos/fixtures/tier1_backtest_summary.json`

**Interfaces:**
- `run_tier1_backtest(fixture_path) -> dict` with `spearman_rho`, `n_weeks`, `baseline_rho`
- Test asserts committed summary matches within tolerance (regression lock)

- [ ] **Step 1–4: Implement + commit summary**

- [ ] **Step 5: Commit** `test: SoS Tier1 offline backtest harness`

---

### Task 7: Web — L4/L8/season + Tier1 view

**Files:**
- Modify: `apps/web/src/week/types.ts`, `api/client.ts`
- Modify: `apps/web/src/week/WeekSosView.tsx`, `WeekSosView.test.tsx`

**Interfaces:**
- Toggle: **Classic (FPA/PAE)** vs **Tier 1 (shrunk aFPA)** — default Tier 1 in UI when feature shipped
- Window: L4 | **L8** | Season (only in Tier 1 mode)
- Opportunity section: league select + table sorted by `opportunity` desc
- Colors: use bucket not raw rank gradient when Tier 1 active

- [ ] **Step 1: vitest** fetch tier1 URL with `window=l8`

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat: SoS Tier1 UI with L8 default and opportunity table`

---

### Task 8: README + verification

- [ ] Update `apps/api/src/draft_api/sos/README.md` with Tier 1 section
- [ ] `uv run --package draft-api pytest apps/api/tests/sos -v`
- [ ] `pnpm test -- WeekSosView`
- [ ] Manual: compare Week 8+ ranks stability vs classic FPA

---

## Spec coverage

| Design item | Task |
|-------------|------|
| L8 default, L4/L8/season | 1, 5, 7 |
| Empirical-Bayes shrink | 1 |
| Top-7 / mid / bottom-7 | 1 |
| opportunity = softness × share | 2, 3 |
| Backtest | 6 |
| Roster join | 4, 5 |
| DST excluded from opportunity | 3, 4 |

## Placeholder self-review

- P1 `espn_roster.py` dependency: Task 4 notes fallback — implement workbook P1 first or inline minimal fetch to unblock Tier 1.
- No breaking changes to existing SoS query params.
