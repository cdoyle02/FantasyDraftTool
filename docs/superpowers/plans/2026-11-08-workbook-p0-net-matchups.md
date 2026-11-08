# Workbook P0 Net Matchups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship P0 of the Workbook: weekly Net Matchups board (Game Environment + QB/WR Out/Slot/TE/RB), feeder + explain APIs, window/scoring/slate controls, nflverse snapshot fallback, and a Workbook web tab.

**Architecture:** New `draft_api/workbook/` package mirrors `draft_api/sos/` (pure calc → nflverse loader → snapshot → service → FastAPI routes → Vite React tab). Spec: `docs/superpowers/specs/2026-11-08-workbook-net-matchups-design.md`.

**Tech Stack:** Python 3.13 + FastAPI (`apps/api`), nflverse CSV releases (PBP + FTN charting/alignment + schedules + odds reuse), React/Vite (`apps/web`), vitest, pytest via `pnpm test:python` / `pnpm test`.

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-11-08-workbook-net-matchups-design.md`
- Do **not** scrape Majesstik’s Google Sheet; compute from nflverse + `week_odds`
- Net rate stats: `(OFF + OppDEF) / 2`; Comb Net DSR = mean of both teams’ Net DSR; Diff = team − opponent
- Window default **L4**; scoring default **PPR** (Half-PPR toggle); slate `main` | `all` as defined in spec
- Out/Slot: WR-only alignment; TE/RB in slot excluded; thin sample or missing source → `null` + `insufficient_alignment_sample`. Public FTN charting lacks alignment — Task 5.5 finds a source; do not invent Out/Slot from `pass_location`
- Never read/print/commit `.env`, ESPN cookies, or Odds API keys
- Pattern-match `draft_api/sos/` (TtlCache 6h, snapshot `stale: true`, `error_response` codes)
- P0 only — no ESPN overlay, MCP, TOP/Pace/Injuries/Matrix/DFS pool (P1–P3)
- SoS uncommitted work in the tree may exist; do not revert it; keep Workbook changes scoped

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/workbook/__init__.py` | Package marker |
| `apps/api/src/draft_api/workbook/calculate.py` | Pure OFF/DEF/Net, DSR, PROE, explosives, windows, matchup rows |
| `apps/api/src/draft_api/workbook/alignment.py` | Classify WR targets as outside vs slot |
| `apps/api/src/draft_api/workbook/fantasy.py` | PPR / half-PPR from receiving/rushing/passing components |
| `apps/api/src/draft_api/workbook/nflverse.py` | Download/normalize PBP (+ alignment join), schedules, team weeks |
| `apps/api/src/draft_api/workbook/identity.py` | Team abbrev map (reuse SoS aliases) |
| `apps/api/src/draft_api/workbook/snapshot.py` | Read/write packaged `workbook_{season}.json` |
| `apps/api/src/draft_api/workbook/service.py` | Cache, live→snapshot, build matchups/feeders/explain |
| `apps/api/src/draft_api/workbook/refresh.py` | CLI refresh snapshot |
| `apps/api/src/draft_api/workbook/README.md` | Metric SSOT |
| `apps/api/src/draft_api/data/workbook_2026.json` | Packaged snapshot |
| `apps/api/src/draft_api/main.py` | Three GET routes |
| `apps/api/tests/workbook/…` | pytest |
| `apps/web/src/week/types.ts` | Workbook response types |
| `apps/web/src/api/client.ts` | Client methods |
| `apps/web/src/week/WeekWorkbookView.tsx` | Board UI |
| `apps/web/src/week/WeekWorkbookView.test.tsx` | vitest |
| `apps/web/src/App.tsx` | Workbook tab |

---

### Task 1: Net helpers + fantasy scoring (pure)

**Files:**
- Create: `apps/api/src/draft_api/workbook/__init__.py`
- Create: `apps/api/src/draft_api/workbook/fantasy.py`
- Create: `apps/api/src/draft_api/workbook/calculate.py` (helpers only first)
- Test: `apps/api/tests/workbook/test_fantasy_and_net.py`

**Interfaces:**
- Produces:
  - `mean_net(off: float | None, opp_def: float | None) -> float | None`
  - `comb_net_dsr(a: float | None, b: float | None) -> float | None`
  - `net_dsr_diff(team_net: float | None, opp_net: float | None) -> float | None`
  - `receiving_points(*, receptions: float, yards: float, tds: float, scoring: Literal["ppr","half_ppr"]) -> float`
  - `rushing_points(*, yards: float, tds: float) -> float`
  - `passing_points(*, yards: float, tds: float, ints: float = 0) -> float` (0.04/yd, 4/TD, −2/INT)

- [ ] **Step 1: Write failing tests**

```python
from draft_api.workbook.calculate import comb_net_dsr, mean_net, net_dsr_diff
from draft_api.workbook.fantasy import receiving_points


def test_mean_net_averages():
    assert mean_net(10.0, 20.0) == 15.0
    assert mean_net(None, 20.0) is None


def test_comb_and_diff():
    assert comb_net_dsr(0.6, 0.8) == 0.7
    assert net_dsr_diff(0.7, 0.5) == 0.2


def test_ppr_vs_half():
    assert receiving_points(receptions=5, yards=50, tds=1, scoring="ppr") == 16.0
    assert receiving_points(receptions=5, yards=50, tds=1, scoring="half_ppr") == 13.5
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /Users/michaeldoyle/repos/FantasyDraftTool && uv run --package draft-api pytest apps/api/tests/workbook/test_fantasy_and_net.py -v`  
Expected: FAIL (import / not found)

- [ ] **Step 3: Implement minimal helpers** in `fantasy.py` + `calculate.py`

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/draft_api/workbook/__init__.py \
  apps/api/src/draft_api/workbook/fantasy.py \
  apps/api/src/draft_api/workbook/calculate.py \
  apps/api/tests/workbook/test_fantasy_and_net.py
git commit -m "$(cat <<'EOF'
Add Workbook Net helpers and PPR/half-PPR scoring.

EOF
)"
```

---

### Task 2: DSR + explosives + PROE (pure)

**Files:**
- Modify: `apps/api/src/draft_api/workbook/calculate.py`
- Test: `apps/api/tests/workbook/test_dsr_proe.py`

**Interfaces:**
- Consumes: Task 1 helpers
- Produces:
  - `@dataclass(frozen=True, slots=True) class DriveOutcome: team: str; week: int; success: bool`  # success = first down or TD; kneels excluded upstream
  - `drive_success_rate(drives: list[DriveOutcome], *, team: str, weeks: set[int]) -> float | None`
  - `explosive_pass(yards: float) -> bool`  # > 15
  - `explosive_run(yards: float) -> bool`   # > 10
  - `@dataclass(frozen=True, slots=True) class PassPlay: team: str; week: int; is_pass: bool; xpass: float | None`
  - `pass_rate_over_expectation(plays: list[PassPlay], *, team: str, weeks: set[int]) -> float | None`  
    - Include only plays with `xpass is not None`; PROE = mean(`is_pass` as 0/1 − `xpass`) × 100 (percentage points), matching common nflfastR display

- [ ] **Step 1: Failing tests** for DSR (2/3 success → ~0.666), kneel-excluded sample provided by caller, explosives thresholds, PROE with known xpass

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit** `feat: add Workbook DSR, explosives, and PROE calculators`

---

### Task 3: WR alignment classifier

**Files:**
- Create: `apps/api/src/draft_api/workbook/alignment.py`
- Test: `apps/api/tests/workbook/test_alignment.py`

**Interfaces:**
- Produces:
  - `Alignment = Literal["outside", "slot", "other"]`
  - `classify_wr_alignment(*, position: str, alignment_raw: str | None) -> Alignment | None`  
    - If `position` not in `{"WR"}` → `None` (exclude TE/RB even if lined up slot)
    - Map FTN/nflverse strings case-insensitively: values containing `slot` → `slot`; `wide` / `outside` / `boundary` → `outside`; else `other`
  - Document exact raw strings discovered in Task 5 README once a real CSV sample is inspected

- [ ] **Step 1: Tests** — WR+slot → slot; TE+slot → None; WR+wide → outside; missing → other or None per chosen rule (`None` only for non-WR)

- [ ] **Step 2–4: TDD cycle**

- [ ] **Step 5: Commit** `feat: classify Workbook Outside vs Slot WR alignment`

---

### Task 4: Window selection + OFF/DEF aggregates + matchup Net row

**Files:**
- Modify: `apps/api/src/draft_api/workbook/calculate.py`
- Test: `apps/api/tests/workbook/test_matchup_net.py`

**Interfaces:**
- Produces:
  - `resolve_stat_weeks(*, mode: Literal["l4","season","custom"], rated_through_week: int, custom_start: int | None, custom_end: int | None) -> set[int]`  
    - `l4`: last 4 completed weeks ending at `rated_through_week` (e.g. rated 8 → {5,6,7,8})
    - `season`: `{1..rated_through_week}`
    - `custom`: inclusive range clipped to 1..18
  - `@dataclass` team-week rate bags as needed (keep small): e.g. `TeamRateSlice` with fields used on the board
  - `build_game_environment_net(*, team_off: TeamEnvRates, opp_def: TeamEnvRates, team_net_dsr: float | None, opp_net_dsr: float | None, implied_points: float | None) -> dict[str, float | None]`  
    Keys match camelCase API later: `netDsr`, `combNetDsr`, `netDsrDiff`, `netProe`, `netPassPlays`, `netEpaPass`, `netXplsvPass`, `netRunPlays`, `netEpaRun`, `netXplsvRun`, `vegasImpliedPoints`
  - `build_positional_net(off: dict[str, float | None], opp_def: dict[str, float | None]) -> dict[str, float | None]` using `mean_net` per key
  - `is_main_slate(weekday_local: int, kickoff_hour_local: int) -> bool`  
    - Spec: main = Sunday early+late only. Treat `weekday==6` (Sun) and kickoff hour `< 19` America/Chicago as main; else not. (Document; adjust only with test update.)

- [ ] **Step 1: Fixture** two teams with known OFF/DEF rates → assert Net averages, Comb/Diff, L4 week set, main-slate Sunday 12:00 True / Mon False / Sun 19:00 False

- [ ] **Step 2–4: TDD**

- [ ] **Step 5: Commit** `feat: build Workbook game-environment and positional Net rows`

---

### Task 5: nflverse loader (fixture CSV, no network in CI)

**Files:**
- Create: `apps/api/src/draft_api/workbook/identity.py` (export `normalize_team`, `NFL_TEAMS`, reuse aliases from `draft_api.sos.nflverse.TEAM_ALIASES` or duplicate constant to avoid circular imports — prefer import from sos if stable)
- Create: `apps/api/src/draft_api/workbook/nflverse.py`
- Create: `apps/api/tests/workbook/fixtures/` tiny gzipped or plain CSV snippets (PBP rows + alignment join keys)
- Test: `apps/api/tests/workbook/test_nflverse.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class WorkbookDataset:` season, fetched_at, teams, schedule (week→team→opponent|bye), drives, pass_plays, team_env_off, team_env_def, positional_off, positional_def (including `all_wr` / `out_wr` / `slot_wr` / `te` / `rb` / `qb` rate dicts keyed by team→week)
  - `load_workbook_dataset(season: int, *, http_get: HttpGetter | None = None, now: datetime | None = None) -> WorkbookDataset`
  - URLs (lock in module constants; verify against current nflverse release layout when implementing):
    - PBP: `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz`
    - FTN charting (alignment): inspect release assets named like `ftn_charting_{season}.csv.gz` — if naming differs, update constant + README in same commit
    - Schedules: reuse SoS `SCHEDULES_URL` / games.csv
  - Join alignment to PBP on `game_id` + `play_id` (or documented keys)
  - Raise `WorkbookNflverseError` on HTTP/parse failure

- [ ] **Step 1: Add minimal fixture CSVs** covering one game, WR slot + outside targets, one drive success/fail, one pass with xpass

- [ ] **Step 2: Failing test** `load_workbook_dataset` via `http_get` returning fixture bytes by URL suffix

- [ ] **Step 3: Implement parser + normalizer** (stream CSV; do not load full season into tests)

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: load Workbook datasets from nflverse PBP and alignment`

---

### Task 5.5: Find Out/Slot WR alignment data source

**Files:**
- Create: `docs/superpowers/specs/2026-11-08-workbook-alignment-source-research.md` (decision record)
- Modify (only if a source is chosen and wireable in this task): `apps/api/src/draft_api/workbook/nflverse.py`, `README.md`, fixtures/tests
- Modify: `docs/superpowers/specs/2026-11-08-workbook-net-matchups-design.md` (lock chosen source in Decisions table)

**Goal:** Replace the public-FTN gap with a concrete, household-viable source so Out/Slot can be full fidelity — or document that P0 ships with null Out/Slot and name the P1 wire-up.

**Interfaces:**
- Research deliverable must answer: source name, license/cost, refresh cadence, join keys to nflverse PBP (`game_id`/`play_id` or equivalent), WR-only filter feasibility, and recommended next implementation step.
- Candidates to evaluate (non-exhaustive): FTN Participation Feed (`skp_pos`), Next Gen Stats / nflverse NGS, Sports Info Solutions / PFF (paid), household-maintained supplemental CSV matching `ALIGNMENT_COLUMN=receiver_alignment`, other open nflverse releases.
- Do **not** approximate from `pass_location` unless the decision record explicitly accepts degraded fidelity and UI labels it.
- Do **not** scrape Majesstik’s sheet.
- Never commit secrets / paid API keys.

- [ ] **Step 1: Survey** each candidate (availability 2025–2026, columns, cost, join path) — use Exa/web + nflverse docs; optional one-time public sample inspect
- [ ] **Step 2: Write decision record** at the path above with ranked options + recommendation
- [ ] **Step 3: If a free/wireable source exists** — implement loader hook + fixture test in the same commit series; else stop after the decision record and amend the design Decisions row to name the deferred source
- [ ] **Step 4: Commit** docs (and code only if wired)

---

### Task 6: Snapshot + refresh CLI

**Files:**
- Create: `apps/api/src/draft_api/workbook/snapshot.py`
- Create: `apps/api/src/draft_api/workbook/refresh.py`
- Create: `apps/api/src/draft_api/data/workbook_2026.json` (generated; may be slim synthetic for first commit if live refresh deferred)
- Test: `apps/api/tests/workbook/test_snapshot.py`

**Interfaces:**
- Produces:
  - `read_packaged_snapshot(season: int) -> WorkbookDataset`
  - `write_snapshot(path: Path, dataset: WorkbookDataset) -> None`
  - `python -m draft_api.workbook.refresh --season 2026` writes `data/workbook_2026.json`
- Mirror SoS snapshot error type pattern (`SnapshotError`)

- [ ] **Step 1–4: TDD** round-trip serialize synthetic dataset

- [ ] **Step 5: Commit** `feat: add Workbook snapshot package and refresh command`

**Note:** Full-season live refresh can be run once before ship; CI must not require network.

---

### Task 7: Service layer (cache, stale, matchups/feeders/explain)

**Files:**
- Create: `apps/api/src/draft_api/workbook/service.py`
- Create: `apps/api/src/draft_api/workbook/README.md` (metric definitions)
- Test: `apps/api/tests/workbook/test_service.py`

**Interfaces:**
- Consumes: `WorkbookDataset`, calculate builders, `draft_api.implied_totals` / week odds **optional**: if odds unavailable, `vegasImpliedPoints` is `null` (do not fail the board)
- Produces:
  - `build_matchups_response(*, week: int, window: str, scoring: str, slate: str, season: int, now: datetime | None) -> dict`
  - `build_feeder_response(*, group: str, window: str, scoring: str, season: int, ...) -> dict`
  - `build_explain_response(*, team: str, week: int, metric: str, window: str, scoring: str, season: int, ...) -> dict`
  - Test hooks: `set_workbook_dataset_override`, `clear_workbook_cache` (copy SoS pattern)
- Response shape (matchups) — lock:

```json
{
  "season": 2026,
  "week": 10,
  "window": "l4",
  "scoring": "ppr",
  "slate": "main",
  "ratedThroughWeek": 9,
  "fetchedAt": "...",
  "source": "nflverse",
  "stale": false,
  "attribution": "Computed by FantasyDraftTool from nflverse + odds. Methodology inspired by Majesstik/OWS Workbook; not their sheet.",
  "games": [
    {
      "away": "NE",
      "home": "NYJ",
      "kickoff": "2026-11-09T18:00:00Z",
      "mainSlate": true,
      "rows": [
        {
          "team": "NE",
          "homeAway": "away",
          "opponent": "NYJ",
          "gameEnvironment": { "vegasImpliedPoints": 16.5, "netDsr": 0.69 },
          "qb": { "fpGTot": 10.9 },
          "allWr": {},
          "outWr": { "fpG": null, "reason": "insufficient_alignment_sample" },
          "slotWr": {},
          "te": {},
          "rb": {}
        }
      ]
    }
  ]
}
```

- [ ] **Step 1: Service tests** with dataset override — L4 window, half_ppr changes FP, slate filters Mon game when `main`, stale path via forced loader error + snapshot

- [ ] **Step 2–4: TDD**

- [ ] **Step 5: Commit** `feat: assemble Workbook matchups, feeder, and explain payloads`

---

### Task 8: FastAPI routes

**Files:**
- Modify: `apps/api/src/draft_api/main.py`
- Test: `apps/api/tests/workbook/test_api_workbook.py` (FastAPI TestClient, mirror `tests/sos/test_api_sos.py`)

**Interfaces:**
- `GET /api/v1/nfl/workbook/matchups?week=&window=l4|season|custom&startWeek=&endWeek=&scoring=ppr|half_ppr&slate=main|all&season=2026`
- `GET /api/v1/nfl/workbook/feeders/{group}` same query params; `group` in `dsr|qb|wr|te|rb|targets|yards|tds`
- `GET /api/v1/nfl/workbook/explain?team=&week=&metric=&…`
- Errors: 400 invalid params; 503 `workbook_unavailable`

- [ ] **Step 1: API tests** with dataset override fixture

- [ ] **Step 2–4: Wire routes**

- [ ] **Step 5: Commit** `feat: expose Workbook matchups, feeders, and explain API routes`

---

### Task 9: Web types + client + Workbook tab

**Files:**
- Modify: `apps/web/src/week/types.ts`
- Modify: `apps/web/src/api/client.ts`
- Create: `apps/web/src/week/WeekWorkbookView.tsx`
- Create: `apps/web/src/week/WeekWorkbookView.test.tsx`
- Modify: `apps/web/src/App.tsx` (add Workbook tab next to SoS)

**Interfaces:**
- `draftApi.workbookMatchups(params)`, `workbookFeeders(group, params)`, `workbookExplain(params)`
- UI: week select, window (L4 / season / custom), scoring toggle, slate toggle, heat table by game pair, click cell → explain panel (fetch explain endpoint), attribution footer, stale banner
- Reuse SoS-like `rankColor` but vs league median rank within the returned board (compute client-side from non-null values: higher Net FP/DSR = greener for offense-friendly metrics)

- [ ] **Step 1: vitest** — mock fetch, assert table + controls + stale text

- [ ] **Step 2: Implement view + App tab**

- [ ] **Step 3: Run** `pnpm test -- WeekWorkbookView` and `pnpm test:python -- apps/api/tests/workbook`  
  Expected: PASS

- [ ] **Step 4: Manual** `pnpm api:dev` + `pnpm dev` — open Workbook tab (snapshot OK if nflverse blocked)

- [ ] **Step 5: Commit** `feat: add Workbook Net Matchups tab to the week UI`

---

### Task 10: P0 verification + README polish

**Files:**
- Modify: `apps/api/src/draft_api/workbook/README.md` (final metric table + URL constants + slate definition)
- Optionally note Workbook in `AGENTS.md` repository map one line (only if editing AGENTS is desired — keep to one bullet under Working rules / map)

- [ ] **Step 1: Run full relevant tests**

```bash
cd /Users/michaeldoyle/repos/FantasyDraftTool
uv run --package draft-api pytest apps/api/tests/workbook -v
pnpm test -- WeekWorkbookView
```

- [ ] **Step 2: Confirm** explain OFF/DEF average equals Net for a fixture metric

- [ ] **Step 3: Commit** `docs: finalize Workbook P0 metric README`

---

## Spec coverage (P0)

| Spec item | Task |
|-----------|------|
| Net Matchups board columns | 4, 7, 9 |
| Out/Slot WR-only classifier + join-ready loader | 3, 5 |
| Out/Slot alignment **source** research / wire | 5.5 |
| L4 / season / custom window | 4, 7 |
| PPR / half-PPR | 1, 7, 9 |
| Slate main/all | 4, 7, 9 |
| Feeders API | 7, 8 |
| Explain-on-click | 7, 8, 9 |
| Snapshot + refresh | 6 |
| Attribution / no sheet scrape | 7 README + response field |
| SoS cross-link, ESPN, MCP, TOP, pool | **Out of P0** (P1–P3) |

## Placeholder / consistency self-review

- No TBD steps; API camelCase keys locked in Task 7 JSON.
- `WorkbookNflverseError` vs SoS `NflverseError` — keep separate to avoid coupling; routes map to `workbook_unavailable`.
- Alignment raw-string map finalized when Task 5 inspects FTN CSV; classifier stays string-based so updates are data-only.
