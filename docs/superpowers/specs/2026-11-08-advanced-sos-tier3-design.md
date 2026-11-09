# Advanced SoS — Tier 3 (ensemble softness)

**Date:** 2026-11-08  
**Status:** Design (not implemented)  
**Depends on:** [Tier 1](./2026-11-08-advanced-sos-tier1-design.md), [Tier 2 Phase A](./2026-11-08-advanced-sos-tier2-design.md), [Tier 2 Phase B](./2026-11-08-advanced-sos-tier2-phase-b-design.md)  
**Related:** Clay Out/Slot SoS ([design](./2026-11-08-sos-clay-out-slot-splits-design.md)) — already shipped as a WR role filter on Tier 1/2; **not** reopened here. FTN play-level alignment is a separate upgrade ([FTN Participation design](./2026-11-08-ftn-participation-upgrade-design.md)).

## Goal

Ship a **Tier 3 ensemble softness** surface that blends Tier 1 aFPA ranks with Tier 2 EPA-allowed ranks (and optionally classic PAE) into one household-readable schedule grid — without scraping FootClan, without changing the Tier 1 default, and without requiring paid FTN Participation.

## Scope lock (one spine)

| In | Out |
|----|-----|
| Ensemble softness score from existing Tier 1 + Tier 2 rates | FootClan HTML scrape / player-intelligence dashboard shell |
| Additive `GET …/tier3` (+ optional opportunity) | Replacing Tier 1 as the default SoS view |
| Confidence / agreement badge when component ranks disagree | Ridge regression PAE as a production dependency (optional later weight only) |
| Reuse Clay `wrRole` query param already on Tier 1/2 | Play-level Out/Slot SoS (belongs to FTN upgrade) |
| Offline/snapshot packaging from day one (Phase B lesson) | New ESPN credential paths |

## Locked decisions

| Topic | Choice |
|-------|--------|
| Softness components | **aFPA rank** (Tier 1) + **EPA-allowed rank** (Tier 2); optional third weight **classic PAE rank** behind `includePae=true` (default off) |
| Blend | Rank → softness score via existing soft/neutral/tough map (1.0 / 0.5 / 0.0), then weighted mean: default **`w_afpa=0.5`, `w_epa=0.5`, `w_pae=0`** |
| Final rank | Sort by ensemble softness descending (1 = softest); same 7 / 18 / 7 bucket labels |
| Positions | QB, RB, WR, TE (DST stays classic FPA grid / Tier 1–2 exclusion) |
| Windows | Same L4 / L8 / season as Tier 1–2 |
| Opportunity | `opportunity = ensembleSoftnessScore × usageShare` with Tier 2 snap filter + game-script when Tier 2 data present; else Tier 1 usage |
| Agreement | If \|rank_afpa − rank_epa\| ≥ 10, set `componentsDisagree: true` and surface a muted UI hint |
| API | Additive only: `GET /api/v1/nfl/strength-of-schedule/tier3`, `GET …/tier3/opportunity` |
| UI | New WeekSosView mode **Tier 3 (ensemble)**; default remains Tier 1 |
| Packaging | Ensemble needs packaged aFPA inputs + EPA + snaps (already required for Tier 2 offline); document refresh fields in `sos/README.md` |
| Secrets | Never read/print/commit ESPN cookies or FTN keys |

## Non-goals

- Scraping or republishing FootClan / Majesstik
- Changing classic FPA/PAE CompletedGame path
- Requiring FTN Participation or Clay PDF changes
- Auto-switching default SoS away from Tier 1
- Player-intelligence dashboard shell (wishlist — separate product track)

## Architecture (proposed)

```
apps/api/src/draft_api/sos/
  tier3.py           # NEW: blend ranks → ensemble softness + opportunity
  service.py         # tier3 response builders (reuse tier1/tier2 loaders)
  README.md          # formulas SSOT
```

No new top-level package. Prefer calling existing shrink/rank helpers rather than duplicating aFPA/EPA math.

## Formulas (SSOT — implement exactly when planned)

For defense `d`, position `p`, window `W`:

```
score_afpa = softness_score(rank_afpa(d,p,W))     # soft→1, neutral→0.5, tough→0
score_epa  = softness_score(rank_epa(d,p,W))
score_pae  = softness_score(rank_pae(d,p,W))      # only if includePae

ensemble = (w_afpa * score_afpa + w_epa * score_epa + w_pae * score_pae)
           / (w_afpa + w_epa + w_pae)

# Missing component → drop its weight from the denominator (do not invent 0.5)
```

Rank all 32 teams by `ensemble` descending → `rank`, buckets 7/18/7.

```
opportunity = ensemble × usageShare   # usageShare from Tier 2 path when available
```

## API shape (additive)

Request mirrors Tier 2: `position`, `window`, optional `season`, `wrRole`, `leagueId`, `includePae`.

Response additions vs Tier 2 team row:

- `ensembleSoftnessScore: number`
- `componentRanks: { afpa: number \| null, epa: number \| null, pae?: number \| null }`
- `componentsDisagree: boolean`
- `weights: { afpa, epa, pae }`

Tier 1 and Tier 2 routes remain unchanged.

## UI

- Mode toggle: Classic / Tier 1 / Tier 2 / **Tier 3 (ensemble)**
- Cell coloring from ensemble rank (reuse softness palette)
- Optional compact chip when `componentsDisagree`
- League availability badges (already on TEAM column) continue to work via `leagueId`

## Success criteria

- Household can compare ensemble vs Tier 1/2 on the same week/position without regressions
- Offline snapshot path can serve Tier 3 when packaged Tier 2 fields exist
- No FootClan scrape; no secrets in repo
- Design stays implementable as a thin blender over existing modules

## Open questions (resolve before coding)

1. Exact default weights after a short offline backtest vs Tier 1-only start/sit proxy  
2. Whether PAE ever graduates into the default blend or stays opt-in forever  
3. Whether opportunity for Tier 3 should always force Tier 2 snap+script even when EPA missing  

## Implementation next step

Write `docs/superpowers/plans/2026-*-advanced-sos-tier3.md` with TDD tasks only after these open questions are locked.
