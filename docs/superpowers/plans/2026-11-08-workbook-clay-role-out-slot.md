# Workbook Clay Role Out/Slot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate Workbook `outWr` / `slotWr` Net columns using free weekly Mike Clay WR/CB PDF roles + nflverse WR week stats (role-based, not play-level).

**Architecture:** New `clay_pdf.py` + `roles.py` produce `player_display_name → slot|outside`. Workbook loader aggregates `stats_player_week` WR rows into existing `out_wr` / `slot_wr` OFF/DEF buckets (replacing the empty FTN-alignment path as the **primary** Out/Slot source). Board/UI already expose those keys; update attribution and column labels.

**Tech Stack:** Python 3.13, FastAPI workbook package, `pypdf` for live PDF text extract, vitest/React for label polish, pytest fixtures (no network in CI).

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-11-08-workbook-clay-role-out-slot-design.md`
- Classify: Slot if `Slot% ≥ 45`, else if Pos=`S`, else outside; WR only
- Clay team aliases: `ARZ→ARI`, `BLT→BAL`, `CLV→CLE`, `HST→HOU` (+ existing SoS aliases)
- Unlisted WRs: ALL WR only; never invent Out/Slot
- Bye/missing: last-known role cache; never-seen → omit
- PDF/parse fail → null Out/Slot (`clay_unavailable` or keep `insufficient_alignment_sample`); board still serves ALL WR
- UI: **Out/Slot (Clay role)** + attribution; no Majesstik scrape; no secrets
- Prefer TDD; commit frequently; do not break existing workbook/sos tests

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/workbook/clay_pdf.py` | URL, download, PDF→text, parse layout rows |
| `apps/api/src/draft_api/workbook/roles.py` | Classify, aliases, name normalize, last-known merge |
| `apps/api/src/draft_api/workbook/nflverse.py` | Build out_wr/slot_wr from stats + roles |
| `apps/api/src/draft_api/workbook/service.py` | Attribution string; optional reason code |
| `apps/api/src/draft_api/workbook/README.md` | Document Clay role method |
| `apps/api/tests/workbook/fixtures/clay_wrcb_week9_layout.txt` | Offline layout text sample |
| `apps/api/tests/workbook/fixtures/clay_roles_mini.json` | Tiny role map for loader tests |
| `apps/api/tests/workbook/test_clay_pdf.py` | Parse/classify tests |
| `apps/api/tests/workbook/test_clay_roles_aggregate.py` | Loader Out/Slot fill tests |
| `apps/web/src/week/WeekWorkbookView.tsx` | Column labels |
| `apps/web/src/week/WeekWorkbookView.test.tsx` | Assert Clay role label / attribution |

---

### Task 1: Parse + classify (pure, fixture text)

**Files:**
- Create: `apps/api/src/draft_api/workbook/clay_pdf.py`
- Create: `apps/api/src/draft_api/workbook/roles.py`
- Create: `apps/api/tests/workbook/fixtures/clay_wrcb_week9_layout.txt` (subset of real Week 9 `pdftotext -layout` output including Shakir, Downs, Chase, Franklin conflict, Metchie conflict)
- Test: `apps/api/tests/workbook/test_clay_pdf.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class ClayWrRow: team: str; name: str; pos: Literal["L","S","R"]; lwr_pct: int; slot_pct: int; rwr_pct: int`
  - `parse_clay_layout_text(text: str) -> list[ClayWrRow]`
  - `normalize_clay_team(team: str) -> str`  # ARZ→ARI etc. then `normalize_team`
  - `classify_clay_role(row: ClayWrRow) -> Literal["slot","outside"]`  # Slot%≥45 else Pos==S else outside
  - `normalize_player_name(name: str) -> str`  # lower, strip punctuation variants for join

- [ ] **Step 1: Write failing tests** — Shakir→slot, Chase→outside, Franklin Pos=S Slot=43→slot (Pos rule), Metchie Pos=R Slot=51→slot (pct rule), ARZ→ARI

- [ ] **Step 2: Run** `uv run --directory apps/api pytest tests/workbook/test_clay_pdf.py -v` → FAIL

- [ ] **Step 3: Implement** parser + classifier (no network, no pypdf yet)

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: parse Clay WR roles from cheat-sheet layout text`

---

### Task 2: Live PDF fetch + text extract

**Files:**
- Modify: `apps/api/src/draft_api/workbook/clay_pdf.py`
- Modify: `apps/api/pyproject.toml` (or workspace deps) — add `pypdf` if not present
- Test: extend `test_clay_pdf.py` with bytes→text using a **tiny committed PDF fixture** OR mock `PdfReader`; prefer extracting once to layout txt for CI and unit-test `extract_text_from_pdf_bytes` with a minimal hand-made PDF if easy, else mock

**Interfaces:**
- Produces:
  - `CLAY_PDF_URL_TEMPLATE = "https://g.espncdn.com/s/ffldraftkit/{yy}/NFL{yy}_CS_WRCB.pdf"` with `yy = season % 100`
  - `fetch_clay_pdf_bytes(season: int, *, http_get: Callable[[str], bytes] | None = None) -> bytes`
  - `extract_layout_text_from_pdf(data: bytes) -> str`
  - `load_clay_wr_rows(season: int, *, http_get=None) -> list[ClayWrRow]`  # fetch→extract→parse; raises `ClayPdfError` on failure

- [ ] **Step 1–4: TDD** — http_get returns fixture bytes or layout path; failure raises `ClayPdfError`

- [ ] **Step 5: Commit** `feat: download and extract Clay WR/CB cheat sheet PDF`

---

### Task 3: Last-known role map + name join helpers

**Files:**
- Modify: `apps/api/src/draft_api/workbook/roles.py`
- Test: `apps/api/tests/workbook/test_clay_roles.py`

**Interfaces:**
- Produces:
  - `Role = Literal["slot","outside"]`
  - `build_role_index(rows: list[ClayWrRow]) -> dict[str, Role]`  # key = `normalize_player_name(name)`
  - `merge_last_known(current: dict[str, Role], previous: dict[str, Role] | None) -> dict[str, Role]`  # current overrides; keep previous for missing keys
  - `lookup_role(index: dict[str, Role], player_display_name: str) -> Role | None`

- [ ] **Step 1–4: TDD** merge keeps bye-week player; exact name lookup

- [ ] **Step 5: Commit** `feat: Clay role index with last-known bye carryover`

---

### Task 4: Aggregate Out/Slot OFF/DEF from stats + roles

**Files:**
- Modify: `apps/api/src/draft_api/workbook/nflverse.py`
- Create: `apps/api/tests/workbook/fixtures/clay_roles_mini.json`
- Test: `apps/api/tests/workbook/test_clay_roles_aggregate.py`

**Interfaces:**
- Consumes: `build_role_index` / `lookup_role`; existing `parse_positional_stats` / `PositionalWeekRate` / `receiving_points`
- Change: When building workbook dataset, **prefer Clay role aggregation** for `out_wr`/`slot_wr` over empty FTN alignment bags:
  - For each WR row in `stats_player_week` (REG): `role = lookup_role(...)`; if None, skip Out/Slot (still counts in `all_wr` via existing path)
  - OFF: add that week’s receiving fantasy/targets/yards/TDs to `(team, week)` out or slot bag
  - DEF: add to `(opponent_team, week)` out or slot bag
- Keep FTN alignment path as optional secondary only if it produces samples; Clay is primary for P0.5 (simplest: **replace** alignment-based out/slot fill with Clay role fill; leave `parse_alignment_csv` unused for rates)

- [ ] **Step 1: Fixture** two WRs (slot + outside), one defense week → assert `positional_off["slot_wr"]` / `out_wr` and def mirrors

- [ ] **Step 2–4: TDD** against `load_workbook_dataset` with http_get doubles + injected roles **or** pure helper `aggregate_out_slot_from_stats(stats_rows, role_index) -> ...` called from loader (prefer extractable helper for testability)

- [ ] **Step 5: Commit** `feat: fill Workbook Out/Slot nets from Clay roles and nflverse WR stats`

---

### Task 5: Wire into load/refresh + service attribution

**Files:**
- Modify: `apps/api/src/draft_api/workbook/nflverse.py` (`load_workbook_dataset`)
- Modify: `apps/api/src/draft_api/workbook/service.py` (attribution text)
- Modify: `apps/api/src/draft_api/workbook/README.md`
- Modify: `apps/api/src/draft_api/workbook/refresh.py` if needed to persist role cache inside snapshot JSON

**Interfaces:**
- `load_workbook_dataset`: try `load_clay_wr_rows`; on `ClayPdfError` log warning and use previous roles from snapshot if present else empty index
- Attribution includes: `Out/Slot roles from ESPN Mike Clay WR/CB cheat sheet (role-based); stats from nflverse.`
- Snapshot: optional `clayRoles: { "khalil shakir": "slot", ... }` field round-trip in `snapshot.py`

- [ ] **Step 1–4: Service/loader tests** — with roles, matchups `outWr.fpG` / `slotWr.fpG` non-null for fixture team; without roles, reason null path still OK

- [ ] **Step 5: Commit** `feat: wire Clay roles into Workbook load, snapshot, and attribution`

---

### Task 6: Web labels + vitest

**Files:**
- Modify: `apps/web/src/week/WeekWorkbookView.tsx` — column labels `Out WR (Clay)` / `Slot WR (Clay)` or subtitle via attribution only (prefer short labels **Out WR** / **Slot WR** + attribution already carries Clay; ensure attribution visible)
- Modify: `apps/web/src/week/WeekWorkbookView.test.tsx` — expect attribution substring `Clay`

- [ ] **Step 1–4: vitest**

- [ ] **Step 5: Commit** `feat: show Clay role attribution on Workbook Out/Slot`

---

### Task 7: Verify + push-ready

- [ ] Run `uv run --directory apps/api pytest tests/workbook -q`
- [ ] Run `pnpm test -- WeekWorkbookView`
- [ ] Manual optional: `pnpm api:dev` + open Workbook — Out/Slot populated when Clay+stats available
- [ ] Commit any README nits; report remaining unknown (live PDF layout drift)

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Parse Clay PDF / layout | 1–2 |
| Classify Slot%≥45 / Pos=S | 1 |
| Team aliases | 1 |
| Last-known bye carryover | 3 |
| OFF/DEF aggregate + Net | 4–5 |
| Failure → null | 5 |
| Attribution / UI | 5–6 |
| CI offline fixtures | 1, 4 |

## Placeholder self-review

- No TBD steps; Clay is primary Out/Slot fill (FTN alignment path deprioritized, not deleted).
- `pypdf` added only in Task 2; CI parse tests do not require network.
