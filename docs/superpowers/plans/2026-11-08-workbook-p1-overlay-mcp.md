# Workbook P1 ESPN Overlay + SoS Cross-link + MCP

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Layer season-long ESPN context onto the P0 Workbook board: roster/FA player highlights per league+owner, name+team identity join to nflverse, web league selector (Week D/ST pattern), bidirectional SoS ↔ Workbook navigation, and MCP `workbook_week` via `tools/espn-mcp` `draft_bridge`.

**Architecture:** Extend `draft_api/workbook/identity.py` with player join helpers; add optional query params to matchups (and a thin `highlights` builder); fetch ESPN rosters/FA through existing env-cookie patterns (same as Kyle/Jared). Web persists `leagueId` + optional `ownerTeamId` in `localStorage`. MCP mirrors Kyle/Jared bridge style — no cookies in tool args.

**Tech Stack:** Python 3.13 + FastAPI, ESPN fantasy v3 (existing API helpers), React/Vite, pytest/vitest, `tools/espn-mcp` stdio + HTTP.

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-11-08-workbook-net-matchups-design.md` (P1 row)
- Prerequisite: P0 Workbook shipped (`2026-11-08-workbook-p0-net-matchups.md`); Clay Out/Slot (P0.5) may already be live — do not regress
- Never read/print/commit `.env`, ESPN cookies, MCP tokens, or Odds keys
- ESPN auth: server reads `ESPN_S2` / `ESPN_SWID` from env only (mirror `espn_available_dst.py`); MCP uses active profile
- Highlights are **additive** — matchups shape unchanged when overlay params omitted
- Unmatched players: include in response `joinStats` with counts; never invent `playerId` ↔ nflverse mapping
- P1 only — no TOP/Pace/Injuries/Matrix/DFS pool (P2–P3)
- Do not scrape Majesstik; overlay does not change Net math

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/workbook/identity.py` | Team normalize (existing) + `normalize_player_name`, ESPN↔nflverse join index |
| `apps/api/src/draft_api/workbook/espn_overlay.py` | Build `highlights` from league roster + FA + matchups rows |
| `apps/api/src/draft_api/workbook/service.py` | Optional `league_id` / `owner` on matchups; merge highlights |
| `apps/api/src/draft_api/main.py` | Query params on `/workbook/matchups`; optional `GET /workbook/highlights` if split preferred |
| `apps/api/src/draft_api/espn_roster.py` (or extend existing) | Fetch roster + FA for one league (reuse ESPN HTTP patterns) |
| `apps/api/tests/workbook/test_identity_join.py` | Name+team join fixtures |
| `apps/api/tests/workbook/test_espn_overlay.py` | Highlights without live ESPN (fixtures) |
| `apps/api/tests/workbook/test_api_workbook_overlay.py` | TestClient overlay params |
| `apps/web/src/week/types.ts` | `WorkbookHighlights`, `WorkbookJoinStats` |
| `apps/web/src/api/client.ts` | `workbookMatchups({ leagueId, ownerTeamId, … })` |
| `apps/web/src/week/WeekWorkbookView.tsx` | League select, owner/team toggle, row badges, SoS cross-link |
| `apps/web/src/week/WeekWorkbookView.test.tsx` | League select + highlight badges |
| `apps/web/src/week/WeekSosView.tsx` | Cross-link → Workbook with week/position query |
| `apps/web/src/week/WeekSosView.test.tsx` | Link renders |
| `tools/espn-mcp/src/espn_mcp/draft_bridge.py` | `workbook_week(league, week?, owner?, …)` |
| `tools/espn-mcp/src/espn_mcp/server.py` | Register MCP tool |
| `tools/espn-mcp/tests/test_workbook_week.py` | Bridge contract (mock draft_api) |

---

### Task 1: Player name normalization (pure)

**Files:**
- Modify: `apps/api/src/draft_api/workbook/identity.py`
- Test: `apps/api/tests/workbook/test_identity_join.py`

**Interfaces:**
- Produces:
  - `normalize_player_name(name: str) -> str`  # lowercase, strip punctuation, collapse whitespace; match Clay `roles.py` if present — **single shared implementation** (import from `roles` or move to `identity` and re-export from `roles`)
  - `@dataclass(frozen=True, slots=True) class PlayerRef: gsis_id: str | None; espn_player_id: int | None; display_name: str; team: str`
  - `player_join_key(display_name: str, team: str) -> str`  # `f"{normalize_player_name(display_name)}|{normalize_team(team)}"`

- [ ] **Step 1: Failing tests** — `D.J. Moore` / `DJ Moore` equivalence; team alias `WSH`/`WAS`; join key stable

- [ ] **Step 2: Run** `uv run --package draft-api pytest apps/api/tests/workbook/test_identity_join.py -v` → FAIL

- [ ] **Step 3: Implement**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat: workbook player name+team join keys`

---

### Task 2: ESPN roster fetch helper (fixture-tested)

**Files:**
- Create or extend: `apps/api/src/draft_api/espn_roster.py`
- Create: `apps/api/tests/workbook/fixtures/espn_roster_mini.json`
- Test: `apps/api/tests/workbook/test_espn_roster.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class EspnRosterPlayer: player_id: int; full_name: str; nfl_team: str; roster_slot: str; lineup_slot: str | None; injury_status: str | None`
  - `fetch_league_roster(*, league_id: str, season: int, espn_s2: str, swid: str, http_json: HttpJson | None = None) -> list[EspnRosterPlayer]`
  - `fetch_league_free_agents(*, league_id: str, season: int, …, limit: int = 50) -> list[EspnRosterPlayer]`  # mirror `espn_available_dst` paging pattern
  - Raises `EspnRosterError` on HTTP/parse failure

- [ ] **Step 1: Commit fixture** JSON shaped like real `mTeam`/`roster` payload subset (2 teams, 3 players)

- [ ] **Step 2–4: TDD** with `http_json` override — no network in CI

- [ ] **Step 5: Commit** `feat: fetch ESPN league roster and FA for workbook overlay`

---

### Task 3: Map ESPN players → matchup teams (overlay builder)

**Files:**
- Create: `apps/api/src/draft_api/workbook/espn_overlay.py`
- Test: `apps/api/tests/workbook/test_espn_overlay.py`

**Interfaces:**
- Consumes: `WorkbookMatchupsResponse` rows (team abbrev), `list[EspnRosterPlayer]`, optional `owner_team_id: int | None`
- Produces:
  - `@dataclass(frozen=True, slots=True) class WorkbookHighlight: player_id: int; display_name: str; nfl_team: str; matchup_team: str; opponent: str; role: Literal["roster","free_agent","waiver"]; roster_slot: str | None`
  - `build_highlights(*, games: list[GameBlock], roster: list[EspnRosterPlayer], free_agents: list[EspnRosterPlayer], owner_team_id: int | None) -> tuple[list[WorkbookHighlight], dict[str, int]]`  
    - Match player `nfl_team` to board row `team` via `normalize_team`
    - `join_stats`: `{ "matched": n, "unmatched_team": n, "unmatched_name_only": n }`
  - JSON camelCase: `highlights[]`, `joinStats`

- [ ] **Step 1: Tests** — roster WR on NE highlights NE row when NE plays; FA with correct team; wrong team → unmatched bucket

- [ ] **Step 2–4: TDD**

- [ ] **Step 5: Commit** `feat: build Workbook ESPN highlight list from rosters`

---

### Task 4: Wire overlay into matchups service + API

**Files:**
- Modify: `apps/api/src/draft_api/workbook/service.py`
- Modify: `apps/api/src/draft_api/main.py`
- Test: `apps/api/tests/workbook/test_api_workbook_overlay.py`

**Interfaces:**
- Query params (optional):
  - `leagueId` — configured league id string (same as Kyle `leagueId`)
  - `ownerTeamId` — ESPN team id for “my roster” filter; when set, only that team’s players in `highlights` with `role=roster`; FA still included if `includeFa=true` (default true)
- On ESPN failure when overlay requested: **200** matchups + `highlights: []` + `overlayError: "espn_unavailable"` (do not fail the board)
- Unknown `leagueId` in `espn_leagues.json` → 404 `league_not_found` only when overlay explicitly requested
- Test hooks: `set_espn_roster_http_json` mirroring main.py Kyle pattern

- [ ] **Step 1: API tests** with roster fixture + dataset override

- [ ] **Step 2–4: Wire service + routes**

- [ ] **Step 5: Commit** `feat: optional ESPN highlights on workbook matchups API`

---

### Task 5: Web — league select + highlight badges (WeekDstView pattern)

**Files:**
- Modify: `apps/web/src/week/types.ts`
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/week/WeekWorkbookView.tsx`
- Modify: `apps/web/src/week/WeekWorkbookView.test.tsx`

**Interfaces:**
- Constants: `WORKBOOK_LEAGUE_STORAGE_KEY = 'workbook-league-id'` (mirror `LEAGUE_STORAGE_KEY` in `WeekDstView.tsx`)
- On mount: `draftApi.espnLeagues()` → populate `<select data-testid="workbook-league-select">`
- Persist `leagueId` to `localStorage`; refetch matchups when league changes
- UI:
  - League dropdown in control bar (same styling as Kyle section)
  - “Highlight my players” on when `leagueId` set
  - Badge on team row: count of highlighted players (tooltip lists names)
  - Optional checkbox “Include FA” (default on)
- Client passes `leagueId` as query param only when non-empty

- [ ] **Step 1: vitest** — mock leagues + matchups with `highlights`; assert badge count

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat: Workbook ESPN league selector and highlight badges`

---

### Task 6: SoS ↔ Workbook cross-link

**Files:**
- Modify: `apps/web/src/week/WeekWorkbookView.tsx`
- Modify: `apps/web/src/week/WeekSosView.tsx`
- Modify: `apps/web/src/App.tsx` (optional: `shellView` query or shared navigate helper)
- Test: `apps/web/src/week/WeekSosView.test.tsx`, extend `WeekWorkbookView.test.tsx`

**Interfaces:**
- Workbook footer/link: **“See season SoS for {position}”** — sets parent tab to `week-sos` with `position` preserved (default WR from clicked column context if available, else RB)
- SoS header link: **“See this week’s Net board”** — sets `week-sos` → `week-workbook`; pass current NFL week from SoS `ratedThroughWeek + 1` or shared week state
- Minimal approach: lift week via URL hash `#week-workbook?week=10` **or** `sessionStorage` keys `crossLink.week` / `crossLink.position` read on tab mount (prefer sessionStorage to avoid router churn)
- Document keys in both component file comments

- [ ] **Step 1: Tests** — click cross-link calls tab setter / sessionStorage

- [ ] **Step 2–4: Implement** in `App.tsx` tab buttons reading sessionStorage on activate

- [ ] **Step 5: Commit** `feat: cross-link SoS tab and Workbook tab`

---

### Task 7: MCP `workbook_week` via `draft_bridge`

**Files:**
- Modify: `tools/espn-mcp/src/espn_mcp/draft_bridge.py`
- Modify: `tools/espn-mcp/src/espn_mcp/server.py`
- Create: `tools/espn-mcp/tests/test_workbook_week.py`
- Modify: `tools/espn-mcp/README.md` — tool table row

**Interfaces:**
- Tool: `workbook_week`
- Args:
  - `league: str` — name or id (same as `kyle_dst_available`)
  - `week: int | None` — default current fantasy week from API
  - `owner: str | None` — owner display name to resolve `ownerTeamId` via league teams
  - `window: str = "l4"`, `scoring: str = "ppr"`, `slate: str = "main"`
  - `include_highlights: bool = True`
- Returns JSON string:
  - Subset of matchups: games with `rows` trimmed to headline metrics
  - `highlights` when ESPN cookies valid
  - `attribution`, `stale`
- Implementation:
  - `from draft_api.workbook.service import build_matchups_response` (or HTTP self-call to localhost — **prefer in-process** like Kyle)
  - ESPN: `active_config()` cookies + `_league(league)`
  - Resolve owner → team id via existing roster directory helper or one ESPN teams fetch

- [ ] **Step 1: Test** mock `build_matchups_response` + mock roster → JSON shape

- [ ] **Step 2: Register** tool in `server.py` with description for chat agents

- [ ] **Step 3: Manual** `uv run` MCP smoke when API + env available

- [ ] **Step 4: Commit** `feat: MCP workbook_week bridge tool`

---

### Task 8: P1 verification

- [ ] Run `uv run --package draft-api pytest apps/api/tests/workbook -v`
- [ ] Run `pnpm test -- WeekWorkbookView WeekSosView`
- [ ] Run `uv run --directory tools/espn-mcp pytest tests/test_workbook_week.py -v` if present
- [ ] Manual: `pnpm api:dev` + `pnpm dev` — select league, see badges; MCP tool returns board
- [ ] Update `apps/api/src/draft_api/workbook/README.md` — overlay params + join caveats

---

## Spec coverage (P1)

| Spec item | Task |
|-----------|------|
| ESPN season-long overlay | 2–5 |
| Player identity name+team join | 1, 3 |
| League selector (web) | 5 |
| SoS ↔ Workbook cross-link | 6 |
| MCP `workbook_week` | 7 |
| TOP / Pace / Injuries / Matrix / Pool | **Out of P1** (P2–P3) |

## Placeholder self-review

- No TBD steps; overlay errors degrade gracefully without breaking P0 board.
- Owner resolution may need league-specific ESPN team list — document unmatched owners in MCP return `warnings[]`.
- Future: gsis_id join from `data/rosters/current-teams.csv` as secondary index (optional Task 1.5 — only if household needs better match rate).
