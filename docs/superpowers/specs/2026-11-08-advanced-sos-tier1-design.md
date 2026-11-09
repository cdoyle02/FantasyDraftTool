# Advanced SoS — Tier 1 (rolling softness + opportunity)

**Date:** 2026-11-08  
**Status:** Approved (design); implementation: [Tier 1 plan](../plans/2026-11-08-advanced-sos-tier1.md)  
**Depends on:** Existing `draft_api/sos/` FPA/PAE grid (shipped baseline)  
**Related:** Workbook Net Matchups ([design](./2026-11-08-workbook-net-matchups-design.md)) — complementary (weekly Net vs season schedule softness)

## Goal

Upgrade the household SoS tab with **FootClan-inspired** positional softness that is stable early in the season: rolling defensive allowance, empirical-Bayes shrink toward league prior, explicit **soft / neutral / tough** buckets, and an **opportunity score** (schedule softness × projected usage share) joinable to ESPN rosters — without scraping FootClan or licensing their data.

## Locked decisions

| Topic | Choice |
|-------|--------|
| Rolling window default | **L8** (last 8 completed weeks) |
| Window toggle | **L4** / **L8** / **season-to-date** (same control pattern as Workbook `window`; no custom range in Tier 1) |
| Core rate | **aFPA** — allowed fantasy points per game at position, computed over the selected window on completed games only |
| Shrinkage | **Empirical-Bayes** toward league-position prior: shrink team DEF sample with pseudo-count `k` (default `k=4` games); document formula in `sos/README.md` |
| Softness buckets | **Top 7** teams = soft (easiest), **mid 18** neutral, **bottom 7** = tough (hardest) — by rank of shrunk aFPA (rank 1 = most points allowed = softest) |
| Bucket labels | API `softness: "soft" \| "neutral" \| "tough"` plus numeric `rank` 1–32 |
| Opportunity | `opportunity = softness_score × usage_share` where `softness_score` maps soft→1.0, neutral→0.5, tough→0.0 (linear) and `usage_share` is 0–1 from nflverse (position-specific; see below) |
| Positions | QB, RB, WR, TE (skill); **DST excluded from Tier 1 opportunity** (keep existing DST FPA grid unchanged in Tier 1) |
| Scoring | Full PPR for skill positions (match current SoS) |
| Roster join | ESPN `playerId` + name+team via shared `workbook/identity` normalize helpers; optional `GET` query `leagueId` returns `rosterOpportunity[]` |
| Backtest | Offline harness compares start/sit win-rate proxy vs naive FPA window — not a production endpoint; results in `apps/api/tests/sos/fixtures/tier1_backtest_summary.json` |
| UI default metric | Show **aFPA (shrunk)** with bucket coloring; keep legacy **FPA/PAE** toggle until Tier 2 |
| Secrets | Never read/print/commit ESPN cookies or `.env` |

## Non-goals (Tier 1)

- WR1/WR2/Slot split SoS (Tier 2+)
- EPA-based PAE replacement
- Scraping FootClan HTML
- Player intelligence dashboard shell

## Architecture

Extend `draft_api/sos/` — no new top-level package.

```
apps/api/src/draft_api/sos/
  calculate.py       # add shrink_aFpa, softness_bucket, opportunity_score
  usage.py           # NEW: position usage shares from nflverse stats_player_week
  tier1.py           # NEW: assemble Tier1PlayerRow / Tier1TeamRow payloads
  service.py         # window=l4|l8|season; optional league overlay
  roster_join.py     # NEW: thin wrapper → espn roster + identity join
```

### Formulas (SSOT — implement exactly)

**Shrunk aFPA** for defense `d`, position `p`:

```
raw_afpa(d,p) = mean allowed FP to p over completed games in window
prior(p)      = league mean raw_afpa over all defenses in window
n(d,p)        = game count in window
shrunk(d,p)   = (n * raw + k * prior) / (n + k)
```

Rank defenses by `shrunk` descending (higher allowed = softer = better for opposing skill players).

**Softness score** from rank `r` (1 = softest):

```
if r <= 7:  bucket soft,     score = 1.0
elif r >= 26: bucket tough,   score = 0.0
else:        bucket neutral,  score = 0.5
```

**Usage share** (examples; lock in `usage.py`):

| Position | Share proxy |
|----------|-------------|
| RB | `rush_attempts / team_rush_attempts` (window mean) |
| WR / TE | `targets / team_targets` |
| QB | `1.0` for starter only; backup detection → `null` opportunity |

**Opportunity** for player `i` facing defense `d` in week `w`:

```
opportunity_i = softness_score(d, p) * usage_share_i
```

Unmatched roster players: `opportunity: null`, `joinStatus: "unmatched"`.

### API (Tier 1)

- `GET /api/v1/nfl/strength-of-schedule/tier1?position=RB&window=l8&week=10&season=2026`  
  - Returns team schedule cells with `shrunkAfpa`, `rank`, `softness`, opponent context for remainder of season window (reuse grid shape where possible)
- `GET /api/v1/nfl/strength-of-schedule/tier1/opportunity?position=WR&window=l8&week=10&leagueId=`  
  - Returns `players: [{ playerId, name, team, opponent, softness, usageShare, opportunity }]`
- Extend existing endpoint **or** add `metric=afpa_shrunk` to legacy route — pick one in implementation plan (prefer dedicated tier1 paths to avoid breaking FPA/PAE clients)

### UI

- `WeekSosView.tsx`: window toggle **L4 | L8 | Season**; when Tier 1 enabled, default **L8**
- Heat map uses bucket colors (soft green / tough red) with legend
- Link: “Workbook Net this week” (P1 cross-link)
- Optional league dropdown (same storage key as Workbook or SoS-specific — implementation plan chooses `sos-league-id`)

### Backtest (offline)

- Input: canned 2024-ish slice in fixtures (completed games + stats)
- Compare: Tier 1 opportunity ranking vs raw FPA for top-24 RB weekly FP correlation (Spearman)
- Output: committed JSON summary with rho + n; gate: no regression vs baseline FPA by more than agreed epsilon (document in test)

## Errors

- nflverse fail: existing stale snapshot behavior
- `window` invalid → 400
- `leagueId` unknown → 404 on opportunity endpoint only
- ESPN fail → 200 tier1 team grid; opportunity empty + `espn_unavailable`

## Testing

- Pure: shrink with n=0 → prior; n large → raw
- Bucket boundaries: ranks 7, 8, 26, 27
- Opportunity: soft defense × high usage > tough × low usage
- API: tier1 shape, window toggle, stale path
- Roster join fixture without network
- Backtest fixture produces stable rho

## Success criteria

- Household can open SoS, select L8, see stable ranks by Week 6+ without wild small-sample swings
- Katie league opportunity list highlights soft matchups for starters
- Documented formulas match API numbers in explain fixture
- No FootClan scrape; no secrets in repo
