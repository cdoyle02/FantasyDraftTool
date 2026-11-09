# Workbook P3 DFS Pool + OL/DL Proxy Tab

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DFS workflow to the Workbook: **client-side CSV salary paste** into a weekly player pool, **server-side Net-based ranks/tiers** for pasted names, and an **OL vs DL proxy** tab from nflverse pressure/sack/EPA (not Football Outsiders).

**Architecture:** Pool state lives in the browser (Dexie or `sessionStorage` — prefer **sessionStorage** for P3 minimal scope; document upgrade path to Dexie). Server accepts optional `POST /workbook/pool/rank` body with normalized player list + salaries; returns ranks merged from nflverse identity + Workbook Net metrics. OL/DL tab reuses PBP aggregation patterns from P2.

**Tech Stack:** Python 3.13, React/Vite, client CSV parse, pytest/vitest.

## Global Constraints

- Spec SSOT: `docs/superpowers/specs/2026-11-08-workbook-net-matchups-design.md` (P3 row)
- No DraftKings API; no lineup optimizer / sims
- Salaries never sent to server unless user pastes pool (no default upload of DK exports from disk without user action)
- Half-PPR default for pool ranks when `scoring` omitted (DFS household default per spec)
- OL/DL: label **Proxy** in UI; metrics e.g. pressure rate allowed, sack rate, EPA/play allowed — document in README
- Never commit secrets
- Prerequisites: P0 Workbook; P1 identity join strongly recommended for pool name match

---

## File map

| Path | Responsibility |
|------|----------------|
| `apps/api/src/draft_api/workbook/pool.py` | Rank pasted pool against Workbook nets + tertiles |
| `apps/api/src/draft_api/workbook/oldl.py` | OL/DL proxy metrics from PBP |
| `apps/api/src/draft_api/workbook/service.py` | `build_pool_rank_response`, `build_oldl_response` |
| `apps/api/src/draft_api/main.py` | `POST /workbook/pool/rank`, `GET /workbook/oldl` |
| `apps/api/tests/workbook/test_pool.py` | Rank ordering fixtures |
| `apps/api/tests/workbook/test_oldl.py` | Proxy metrics |
| `apps/web/src/week/WeekWorkbookView.tsx` | Sub-nav additions: Pool \| OL/DL |
| `apps/web/src/week/WorkbookPoolView.tsx` | CSV paste UI + rank table |
| `apps/web/src/week/workbookPoolCsv.ts` | Parse DK/FD-ish CSV columns |
| `apps/web/src/week/types.ts` | Pool request/response types |
| `apps/web/src/api/client.ts` | `workbookPoolRank`, `workbookOldl` |

---

### Task 1: CSV parse (client, pure)

**Files:**
- Create: `apps/web/src/week/workbookPoolCsv.ts`
- Create: `apps/web/src/week/workbookPoolCsv.test.ts`
- Create: `apps/web/src/week/fixtures/dk_salaries_sample.csv`

**Interfaces:**
- Produces:
  - `export interface PoolPlayerInput { name: string; team: string; salary: number; position: string; opponent?: string }`
  - `parseDfsCsv(text: string): { players: PoolPlayerInput[]; errors: string[] }`
  - Detect headers: `Name`, `Position`, `Team`, `Salary` (DK); fallback FanDuel column names documented in file header

- [ ] **Step 1–4: vitest** happy path + missing column error

- [ ] **Step 5: Commit** `feat: parse DFS salary CSV for Workbook pool`

---

### Task 2: Server pool rank (identity + Net)

**Files:**
- Create: `apps/api/src/draft_api/workbook/pool.py`
- Test: `apps/api/tests/workbook/test_pool.py`

**Interfaces:**
- Request body:

```json
{
  "week": 10,
  "window": "l4",
  "scoring": "half_ppr",
  "players": [
    { "name": "Ja'Marr Chase", "team": "CIN", "salary": 8200, "position": "WR" }
  ]
}
```

- Produces:
  - `rank_pool(players, *, dataset, week, window, scoring) -> list[PoolRankRow]`
  - `PoolRankRow`: `name`, `team`, `salary`, `position`, `matchupTeam`, `opponent`, `netFpG`, `tier` (tertile from matrices helper), `joinStatus: "matched"|"unmatched"`, `value` (netFpG / salary * 1000 optional computed field)
  - Sort default: `value` desc, then `netFpG` desc
- `POST /api/v1/nfl/workbook/pool/rank` — 400 if >500 players

- [ ] **Step 1–4: TDD** with workbook dataset override + 3-player fixture

- [ ] **Step 5: Commit** `feat: rank DFS pool against Workbook Net metrics`

---

### Task 3: OL/DL proxy tab (server)

**Files:**
- Create: `apps/api/src/draft_api/workbook/oldl.py`
- Test: `apps/api/tests/workbook/test_oldl.py`

**Interfaces:**
- Produces:
  - `@dataclass class OldlTeamRow: team: str; pressure_rate_allowed: float | None; sack_rate_allowed: float | None; epa_per_dropback_allowed: float | None; rank_pressure: int | None`
  - Matchup pairs: each game row shows offense OL proxy vs defense DL proxy (mirror Net board pairing)
- `GET /api/v1/nfl/workbook/oldl?week=&window=…`
- Footer: **“OL/DL proxy from nflverse; not Football Outsiders.”**

- [ ] **Step 1–4: TDD** mini PBP pressure/sack columns (or team aggregates from nflverse team stats if PBP thin)

- [ ] **Step 5: Commit** `feat: Workbook OL/DL proxy metrics`

---

### Task 4: API routes + README

**Files:**
- Modify: `apps/api/src/draft_api/main.py`, `workbook/service.py`, `README.md`
- Test: `apps/api/tests/workbook/test_api_workbook_p3.py`

- [ ] Wire POST + GET; document pool rank limits and identity join caveats

- [ ] **Commit** `feat: Workbook pool rank and OL/DL API routes`

---

### Task 5: Web Pool + OL/DL UI

**Files:**
- Create: `apps/web/src/week/WorkbookPoolView.tsx`
- Modify: `apps/web/src/week/WeekWorkbookView.tsx`
- Test: vitest for paste → rank table

**Interfaces:**
- Pool tab: textarea “Paste DK/FD CSV”, parse preview, button “Rank with Workbook”
- Table columns: Name, Salary, Pos, Opp, Net FP/G, Tier, Value, Match status
- Manual tier override: optional local-only tag `target` | `fade` (sessionStorage) — **non-goal to sync server**
- OL/DL tab: game-pair table like matchups with proxy columns + explain tooltip

- [ ] **Step 1–4: vitest + manual**

- [ ] **Step 5: Commit** `feat: Workbook DFS pool and OL/DL tabs`

---

### Task 6: Verification

- [ ] Full workbook test suite + web tests
- [ ] Manual: paste real DK export (user-local) — no commit of real salaries file

---

## Spec coverage (P3)

| Spec item | Task |
|-----------|------|
| DFS CSV paste pool | 1, 2, 5 |
| Server ranks from Net | 2, 5 |
| Client-side salaries | 1, 5 |
| OL/DL proxy tab | 3, 4, 5 |
| Live DK API / optimizer | **Non-goal** |

## Placeholder self-review

- Pool unmatched names surface clearly; no silent fuzzy match beyond `normalize_player_name` + team.
- sessionStorage pool clears on tab close — documented; Dexie migration noted as future.
