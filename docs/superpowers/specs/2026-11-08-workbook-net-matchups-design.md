# Workbook Net Matchups (Majesstik / OWS-inspired)

**Date:** 2026-11-08  
**Status:** Approved (design); implementation plans per phase  
**Inspiration:** [Majesstik #TheWorkbook](https://docs.google.com/spreadsheets/d/1f-OJbf4l9SIDigrsAMrrjiOU-G4i1Q1NidZkKk2z6C0/edit) · [How to Use #TheWorkbook](https://oneweekseason.com/how-to-use-theworkbook/) · [By The Numbers Guide](https://oneweekseason.com/by-the-numbers-guide/) · tutorial [x.com/majesstik1/status/1702730284410740737](https://x.com/majesstik1/status/1702730284410740737)  
**Note:** We **compute our own** Net Matchups from nflverse + our odds. We do **not** scrape or republish Majesstik’s sheet.

## Goal

Ship a living weekly Workbook in FantasyDraftTool: Game Environment + positional Net Matchups (QB, ALL WR, Outside WR, Slot WR, TE, RB), feeder OFF/DEF/Net tables, season-long ESPN overlays, DFS pool support, supporting tabs (TOP, Pace, OL/DL proxies, Injuries, Positional Matrices), MCP access, and a clear link to the existing SoS heat map — for both season-long and DFS use.

## Decisions

| Topic | Choice |
|-------|--------|
| Approach | Shared weekly **Net engine**; multiple surfaces (web Workbook, ESPN overlay, DFS overlay, MCP). Not a Google Sheet clone UI and not sheet-sync. |
| Scope | Full Workbook product goal, delivered in phases P0–P3 (below). |
| Audience | Season-long (Katie / Michael ESPN) **and** DFS; season-long overlay before DFS salary/pool polish. |
| Out / Slot WR | **Full fidelity when an alignment-bearing source is wired**; Slot counts **WR only** (no TE/RB lined up inside). Public nflverse `ftn_charting` has no per-target slot/outside field (verified 2026-11-08). Until a source is chosen, Out/Slot may be `null` + `insufficient_alignment_sample`; join/classifier stay ready. **Follow-up:** research task to pick a durable alignment source (FTN Participation, NGS, supplemental CSV, etc.) and wire it. |
| Rolling window | UI toggle: **L4 (default)** / season-to-date / custom range (same week-window idea as SoS). |
| Scoring | Toggle: **PPR** (season-long default) / **Half-PPR** (DFS default). |
| Net math | Rate stats: `Net = (OFF + OppDEF) / 2` on a common scale. Volume (plays, targets/G): average of offense-for and defense-allowed. Document per-metric in code + README. |
| Comb Net DSR | Mean of both teams’ Net DSR for that game. **Net DSR Diff** = team Net DSR − opponent Net DSR. |
| Explosives | Pass plays >15 yards; run plays >10 yards (OWS By The Numbers). |
| DSR | Share of drives ending in first down or TD; exclude QB kneels. |
| PROE | From nflverse PBP: actual pass rate minus expected (`xpass` / equivalent). If `xpass` missing for a play, exclude that play from PROE sample. |
| Slate filter | `all` = every game in the NFL week. `main` = Sunday early + late windows only (exclude Thu, Fri, Sat, Sun night, Mon) — documented in README; adjustable if household slate differs. |
| Vegas | Reuse `week_odds` / implied totals; show implied points on Game Environment. |
| SoS relationship | Workbook = **this week’s Net matchup**; SoS tab = **season schedule FPA/PAE**. Cross-link in UI; shared team/week identity. |
| Injuries | ESPN injury/status first; Sunday inactives when a reliable feed exists; tab may be thin early. |
| OL vs DL | **Proxy** from nflverse (pressure/sack/EPA allowed) — not Football Outsiders scrape. Label as proxy in UI. |
| DFS salaries | No live DK API. **CSV paste / upload** into pool; manual tiers always available. |
| Attribution | In-app footer: methodology inspired by Majesstik / OWS; numbers are ours. |
| Secrets | Never read/print/commit ESPN cookies, Odds keys, or `.env` contents. |

## Phases

| Phase | Deliverable |
|-------|-------------|
| **P0** | Net Matchups board + feeder OFF/DEF/Net APIs + explain-on-click + week/slate filter + window/scoring toggles + packaged snapshot + refresh command + web Workbook tab |
| **P1** | ESPN season-long overlay (roster / FA highlights) + SoS ↔ Workbook cross-link + MCP `workbook_week` (board + highlights for a league/owner) |
| **P2** | TOP + Pace tabs; Injuries tab; Positional Matrices with a **documented** tier rubric (not an opaque clone of Majesstik’s unpublished scores) |
| **P3** | DFS player pool (tiers + CSV salary paste); OL vs DL proxy tab |

Implementation plans are written **one phase at a time**, starting with P0.

## Architecture

Mirror `draft_api/sos/`: pure calculators, nflverse loaders, snapshot, service, routes, web client, tests.

```
apps/api/src/draft_api/workbook/
  calculate.py      # OFF / DEF / Net, DSR, PROE, explosives, positional nets
  alignment.py      # Out vs Slot WR classification from PBP
  nflverse.py       # PBP + weekly stats + schedule download/normalize
  snapshot.py       # packaged JSON fallback
  service.py        # assemble API payloads (window, scoring, slate)
  refresh.py        # CLI refresh of snapshot
  identity.py       # P0: team abbrev map (shared with SoS). P1: player gsis↔ESPN join.
  README.md         # metric definitions (SSOT for Net formulas)

apps/web/src/week/
  WeekWorkbookView.tsx   # Net board + controls + explain drawer
  (later) feeder / TOP / pace / injuries / matrix / pool views

data/workbook_2026.json  # packaged snapshot (season in filename)

MCP (tools/espn-mcp or draft_api bridge): workbook_week
```

### API (P0 minimum)

- `GET /api/v1/nfl/workbook/matchups?week=&window=l4|season|start-end&scoring=ppr|half_ppr&slate=main|all`
  - Rows per team for the week’s games: Game Environment + positional Net blocks + color ranks vs league median.
- `GET /api/v1/nfl/workbook/feeders/{group}` — `dsr` | `qb` | `wr` | `te` | `rb` | `targets` | `yards` | `tds`  
  - OFF / DEF / Net columns for drill-down and matrices later.
- `GET /api/v1/nfl/workbook/explain?team=&week=&metric=` — OFF, DEF, Net components for one cell.

Live nflverse cache (~6h, same spirit as SoS). On failure: serve snapshot with `stale: true`.

### P1+ endpoints

- Matchups payload optionally includes `highlights` when `leagueId` (+ owner) provided.
- MCP `workbook_week` wraps matchups + highlights for chat.
- Pool / matrix / TOP / pace / injuries as separate GETs when those phases ship.

### UI

- New **Workbook** tab beside SoS / Week D/ST / K.
- Primary viewport: Net Matchups heat table (game pairs), controls for week, window, scoring, slate.
- Click cell → explain panel (OFF / DEF / Net).
- Feeder tables reachable from the same tab (sub-nav or drawer), not a separate product.
- P1: toggle “highlight my roster / FA” via existing league selector patterns.
- Cross-link: “See season SoS for this position” ↔ “See this week’s Net board.”

### Identity join (P1, designed in P0)

- Canonical team abbreviations (reuse SoS nflverse→app map).
- Player join: nflverse `gsis_id` / name+team → ESPN `playerId` where possible; document unmatched rate; never invent silent mismatches.

## Metric catalog (board columns)

**Game Environment:** Vegas Implied Points, Net DSR, Comb Net DSR, Net DSR Diff, Net PROE, Net Pass Plays, Net EPA/Pass, Net Explosive Pass, Net Run Plays, Net EPA/Run, Net Explosive Run.

**QB Net:** FP/G Tot, FP/G Pass, FP/G Run, Yds/G, Pass TD/G, Sack%.

**ALL WR / Out WR / Slot WR / TE:** FP/G, Tar/G, Tar%, Yd/G, TD/G (WR splits alignment-filtered).

**RB Net:** FP/G Tot, FP Rec, Tar/G, Tar%, Rec Yd/G, Rec TD/G, FP Run, Att/G, Rush Yd/G, Rush TD/G.

Feeder tabs expose the OFF and DEF legs that produce each Net.

## Errors

- nflverse fail + no snapshot → 503 `workbook_unavailable`
- nflverse fail + snapshot → 200 with `stale: true`
- Invalid week/window/scoring → 400
- Unknown league on overlay → 404 (P1)
- Alignment sample too thin for a team/window → still return ALL WR; Out/Slot may be `null` with reason `insufficient_alignment_sample` (prefer null over fake precision)

## Testing

- Pure calc fixtures (DSR, Net average, Comb/Diff, explosives thresholds).
- Alignment: WR-only Slot; TE in slot excluded.
- Parser tests from canned PBP/stats CSV snippets (no network in CI).
- API: matchups shape, window/scoring toggles, stale snapshot path.
- Web: board renders, controls, explain panel (vitest).
- P1+: ESPN highlight join fixtures; MCP contract test when tool ships.

## Non-goals (through P3)

- Scraping or embedding Majesstik’s Google Sheet values.
- Paid PFF / FOA subscriptions as required deps.
- Live DraftKings API or lineup optimizer / sims.
- Clay shadow, Ballers briefing, or full player-intelligence dashboard (may **consume** Workbook Net later).

## Success criteria

- By Tuesday–Sunday of a given NFL week, household can open Workbook, read Game Environment + positional Nets with L4/PPR or Half-PPR, and trust Out/Slot when sample exists.
- Explain-on-click matches feeder OFF/DEF math.
- Snapshot keeps the tab usable if nflverse is down.
- P1: Katie/Michael can see their players highlighted and ask MCP for “Workbook this week.”
- Numbers will not match Majesstik’s sheet exactly (different source refinements); methodology is documented and stable.

## Implementation order

1. Write **P0 implementation plan** (`writing-plans`) → build P0.  
2. Plan + build P1, then P2, then P3.  
3. Advanced SoS Tier 1–3 (rolling aFPA/shrinkage, etc.) remains a **separate** track after Workbook P0 unless explicitly reprioritized.
