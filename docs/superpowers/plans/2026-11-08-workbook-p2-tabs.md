# Workbook P2 Supporting Tabs (TOP, Pace, Injuries, Matrices)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four Workbook sub-tabs beyond the P0 Net Matchups board: **Time of Possession (TOP)**, **Pace (plays per game)**, **Injuries** (ESPN status), and **Positional Matrices** with documented tertile tier rubric — each with dedicated GET APIs and web sub-navigation inside the Workbook tab.

**Architecture:** Extend `draft_api/workbook/` with focused modules (`top.py`, `pace.py`, `injuries.py`, `matrices.py`) that consume the existing `WorkbookDataset` + nflverse PBP where needed. Injuries call ESPN (server env cookies) with offline fixtures in CI. UI uses sub-nav in `WeekWorkbookView` (horizontal pills) mirroring feeder drawer pattern.

**Tech Stack:** Python 3.13, nflverse PBP CSV, ESPN fantasy injury fields, React/Vite, pytest/vitest.

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-11-08-workbook-net-matchups-design.md` (P2 row)
- Prerequisites: P0 Workbook; P1 overlay optional but Injuries tab may reuse ESPN HTTP from P1
- TOP: prefer **drive-level time** from PBP `drive_time_of_possession` / `drive_play_count` when present; fallback **plays-share proxy** = team offensive plays / (team off plays + opponent off plays) per game, labeled `proxy` in API
- Pace: **plays per game** (offensive snaps proxy) — `pass_attempt + rush_attempt + penalties?` per spec in README; exclude spikes/kneels where PBP flags exist
- Injuries: ESPN `injuryStatus` / `injuryBodyPart` first; no scraping Rotowire; tab may be thin early season
- Matrices: **tertile tiers** (top/mid/bottom third of league for selected metric) — not opaque Majesstik scores; tier labels in UI + README rubric
- Never commit secrets; ESPN only via env on server
- Pattern-match existing workbook cache/snapshot/stale semantics

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/workbook/top.py` | TOP % from PBP or plays-share proxy per team/window |
| `apps/api/src/draft_api/workbook/pace.py` | Offensive plays/G, pass/run split |
| `apps/api/src/draft_api/workbook/injuries.py` | ESPN injury payload normalized for board week |
| `apps/api/src/draft_api/workbook/matrices.py` | Tertile bucket assignment from feeder OFF/DEF/Net stats |
| `apps/api/src/draft_api/workbook/service.py` | `build_top_response`, `build_pace_response`, etc. |
| `apps/api/src/draft_api/main.py` | Four new GET routes |
| `apps/api/src/draft_api/workbook/README.md` | TOP/Pace formulas, matrix tier rubric |
| `apps/api/tests/workbook/test_top.py` | PBP fixture TOP |
| `apps/api/tests/workbook/test_pace.py` | Plays/G aggregates |
| `apps/api/tests/workbook/test_injuries.py` | ESPN fixture |
| `apps/api/tests/workbook/test_matrices.py` | Tertile boundaries |
| `apps/api/tests/workbook/test_api_workbook_tabs.py` | Route integration |
| `apps/web/src/week/types.ts` | Response types for four tabs |
| `apps/web/src/api/client.ts` | Client methods |
| `apps/web/src/week/WeekWorkbookView.tsx` | Sub-nav: Matchups \| TOP \| Pace \| Injuries \| Matrices |
| `apps/web/src/week/WeekWorkbookTabs.test.tsx` (or extend existing) | Sub-nav + table smoke |

---

### Task 1: TOP — pure calc + PBP aggregation

**Files:**
- Create: `apps/api/src/draft_api/workbook/top.py`
- Modify: `apps/api/src/draft_api/workbook/nflverse.py` (if new PBP columns needed in dataset)
- Create: `apps/api/tests/workbook/fixtures/pbp_top_mini.csv`
- Test: `apps/api/tests/workbook/test_top.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class TeamTopSlice: team: str; top_pct: float | None; method: Literal["pbp_drive","plays_share_proxy"]; sample_games: int`
  - `top_from_drive_seconds(drives: list[DrivePossession], *, team: str, weeks: set[int]) -> float | None`
  - `top_plays_share_proxy(off_plays: int, opp_off_plays: int) -> float`  # team share 0–1
  - `build_top_table(dataset: WorkbookDataset, *, window, rated_through_week) -> list[TeamTopSlice]`
- Response:
  - `GET /api/v1/nfl/workbook/top?week=&window=l4|season|custom&startWeek=&endWeek=&season=`

- [ ] **Step 1: Fixture** one game — team A 35 plays, team B 25 → proxy TOP 58.3%

- [ ] **Step 2–4: TDD** pure functions first, then loader hook

- [ ] **Step 5: Commit** `feat: Workbook TOP from PBP or plays-share proxy`

---

### Task 2: Pace — plays per game

**Files:**
- Create: `apps/api/src/draft_api/workbook/pace.py`
- Test: `apps/api/tests/workbook/test_pace.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class TeamPaceRow: team: str; plays_per_game: float | None; pass_rate: float | null; run_rate: float | null`
  - `offensive_plays_per_game(plays: list[CountablePlay], *, team: str, weeks: set[int]) -> float | None`
  - Exclude: `play_type` in kneel/spike/no_play when column present
- Response:
  - `GET /api/v1/nfl/workbook/pace?week=&window=…` — same window params as matchups

- [ ] **Step 1–4: TDD** against mini PBP fixture

- [ ] **Step 5: Commit** `feat: Workbook pace plays per game`

---

### Task 3: Injuries — ESPN normalize

**Files:**
- Create: `apps/api/src/draft_api/workbook/injuries.py`
- Create: `apps/api/tests/workbook/fixtures/espn_injuries_mini.json`
- Test: `apps/api/tests/workbook/test_injuries.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class InjuryRow: player_id: int; name: str; team: str; status: str; body_part: str | None; practice: str | None; game_status: str | None`
  - `fetch_week_injuries(*, season: int, week: int, http_json=None) -> list[InjuryRow]`  
    - Source: ESPN consolidated player endpoint or per-team roster injury fields (match P1 roster parser extensions)
  - Sort: team, status severity (Out > Doubtful > Questionable > Probable)
- Response:
  - `GET /api/v1/nfl/workbook/injuries?week=&season=`  
  - `stale` / `source: "espn"`; empty list + `injuries_unavailable` warning when ESPN down (200)

- [ ] **Step 1–4: TDD** fixture only

- [ ] **Step 5: Commit** `feat: Workbook injuries tab data from ESPN`

---

### Task 4: Positional Matrices — tertile tiers

**Files:**
- Create: `apps/api/src/draft_api/workbook/matrices.py`
- Test: `apps/api/tests/workbook/test_matrices.py`

**Interfaces:**
- Consumes: existing feeder OFF/DEF/Net builders (`build_feeder_response` groups)
- Produces:
  - `Tertile = Literal["top","mid","bottom"]`
  - `assign_tertile(values: dict[str, float | None], *, higher_is_better: bool) -> dict[str, Tertile | None]`  
    - Rank 32 teams; top 11 ≈ top tertile, next 10 mid, bottom 11 bottom (document exact cut: `ceil(n/3)` buckets)
  - `build_matrix_payload(*, group: Literal["qb","wr","te","rb","dsr"], metric: str, window, scoring) -> dict`  
    - Rows: teams; cols: OFF / DEF / Net; cell = value + `tier` + color hint
- Response:
  - `GET /api/v1/nfl/workbook/matrices/{group}?metric=fp_per_game|targets_per_game|…&window=…&scoring=…`
- README rubric: tiers are **league-relative for the window**, not absolute FP thresholds

- [ ] **Step 1: Tests** 9-team fixture → 3/3/3 split; null teams omitted from rank pool

- [ ] **Step 2–4: TDD**

- [ ] **Step 5: Commit** `feat: Workbook positional matrices with tertile tiers`

---

### Task 5: Service + API routes

**Files:**
- Modify: `apps/api/src/draft_api/workbook/service.py`
- Modify: `apps/api/src/draft_api/main.py`
- Test: `apps/api/tests/workbook/test_api_workbook_tabs.py`

**Interfaces:**
- All four endpoints share: `season`, `week` (context for rated_through), `window`, custom week range, `scoring` where applicable
- Errors: 400 bad params; 503 `workbook_unavailable` only when dataset missing entirely
- Include `attribution` + `method` field on TOP when proxy

- [ ] **Step 1: Integration tests** with `set_workbook_dataset_override`

- [ ] **Step 2–4: Wire routes**

- [ ] **Step 5: Commit** `feat: expose Workbook TOP Pace Injuries Matrices APIs`

---

### Task 6: Web sub-nav + four views

**Files:**
- Modify: `apps/web/src/week/WeekWorkbookView.tsx` (split inner views or co-located components)
- Modify: `apps/web/src/api/client.ts`, `types.ts`
- Test: extend `WeekWorkbookView.test.tsx`

**Interfaces:**
- Sub-nav `data-testid="workbook-subnav"` — preserves week/window/scoring/slate controls across tabs
- **TOP**: 32-team sortable table, column `TOP %` + badge `proxy` when applicable
- **Pace**: plays/G + pass%
- **Injuries**: filter by team; status chips
- **Matrices**: heat grid with tier letter T/M/B or color; group selector QB/WR/TE/RB/DSR
- Loading/error per sub-view (isolated like Kyle odds vs rankings)

- [ ] **Step 1: vitest** each sub-nav switch triggers correct API path

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat: Workbook supporting tabs UI`

---

### Task 7: README + verification

- [ ] Document formulas in `workbook/README.md`
- [ ] `uv run --package draft-api pytest apps/api/tests/workbook -v`
- [ ] `pnpm test -- WeekWorkbookView`
- [ ] Manual smoke all four tabs

---

## Spec coverage (P2)

| Spec item | Task |
|-----------|------|
| TOP tab | 1, 5, 6 |
| Pace tab | 2, 5, 6 |
| Injuries tab | 3, 5, 6 |
| Positional Matrices + tier rubric | 4, 5, 6 |
| DFS pool / OL-DL | **P3** |

## Placeholder self-review

- TOP proxy is explicitly labeled; upgrade path to drive seconds documented in README.
- Matrices tiers are reproducible from API numbers (explain endpoint may link later).
- Sunday inactives feed is **non-goal** until reliable source — ESPN only in P2.
