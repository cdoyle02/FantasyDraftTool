# Advanced SoS — Tier 2 Phase A

**Date:** 2026-11-08  
**Status:** Approved (design); implementation: [Tier 2 plan](../plans/2026-11-08-advanced-sos-tier2.md)  
**Depends on:** [Tier 1 design](./2026-11-08-advanced-sos-tier1-design.md) (shrunk aFPA + opportunity baseline)

## Goal

Ship Phase A of Tier 2 without breaking Tier 1 or classic FPA/PAE: **snap-filtered usage**, **Vegas game-script adjustment** on opportunity softness, and an **EPA-allowed** defensive rate grid for **QB and RB** with the same rolling-window and softness-bucket semantics as Tier 1.

## Locked decisions (Phase A)

| Topic | Choice |
|-------|--------|
| Snap source | nflverse `snap_counts_{season}.csv.gz` (`offense_pct` 0–1) |
| Min snap filter | **`minOffenseSnapPct = 0.20`** — only player-weeks at or above count toward team volume denominators and numerators |
| Missing snap row | When snap index is supplied, missing player-week → **0%** (excluded from denominators) |
| Snap off (Tier 1) | `build_usage_index` without snap index → unchanged Tier 1 behavior |
| Game script | `week_odds` / `GameLine` implied team total for offense; adjustment applied to **softness score** before × usage |
| Script formula | `delta = clamp((teamImplied - 22.0) / 40.0, -0.15, +0.15)`; `adjustedSoftness = clamp(softnessScore + delta, 0, 1)` |
| No odds | `gameScriptApplied: false`, `delta = 0` |
| EPA allowed (QB) | Per completed game: sum `passing_epa` for QB rows (`team` offense, `opponent_team` defense) |
| EPA allowed (RB) | Per completed game: sum `rushing_epa` for RB rows |
| EPA rank | Higher EPA allowed = **softer** (rank 1 = most EPA allowed), same 7 / 18 / 7 buckets |
| EPA shrink | Same empirical-Bayes as aFPA: `k = 4` toward league mean over the rating window |
| Tier 2 positions (grid) | **QB, RB only** (WR/TE/DST return 400 on tier2 routes) |
| Opportunity (Tier 2) | `opportunity = adjustedSoftness × usageShare` with **EPA-based** softness for QB/RB; snap filter always on when snap data loaded |
| API shape | Additive: `GET …/tier2`, `GET …/tier2/opportunity` — Tier 1 paths unchanged |
| UI | `WeekSosView` view mode **Tier 2 (EPA + script)**; auto-switch to Tier 1 when position ∉ {QB, RB} |

## Non-goals (Phase A)

- WR1 / Slot split SoS
- Ridge PAE, ensemble metrics
- FootClan scrape
- Changing default SoS tab away from Tier 1

## Architecture

```
apps/api/src/draft_api/sos/
  usage.py              # optional snap-filtered denominators (Tier 2)
  tier2_snap.py         # snap_counts parse + lookup index
  tier2_epa.py          # defensive EPA allowed + shrink + ranks
  tier2_game_script.py  # implied-total softness adjustment
  tier2.py              # grid + opportunity assembly (mirrors tier1.py)
  service.py            # tier2 response builders + odds/snap fetch
  README.md             # formulas SSOT
```

## Formulas (SSOT)

### Snap-filtered usage share

For each player-week in the rating window, let `snap = offense_pct` from snap_counts (join on normalized name + team + week).

Eligible player-week iff `snap >= minOffenseSnapPct` (0.20).

Team-week denominator = sum of position volume (carries or targets) over **eligible** players only. Player share for that week = volume / denominator (or skip week if denominator 0). Window share = mean of weekly shares (same as Tier 1, but filtered).

QB: among eligible QB player-weeks, starter = max passing yards in window; starter `usage_share = 1.0` if yards > 0, else `null`.

### Game-script softness adjustment

For offense team `T` in target week `w`:

```
teamImplied = vegas implied points for T (null if no line)
delta = clamp((teamImplied - 22.0) / 40.0, -0.15, 0.15)   # high total → positive delta
adjustedSoftness = clamp(softnessScore + delta, 0.0, 1.0)
```

`opportunity = adjustedSoftness × usageShare`

### Shrunk EPA allowed

For defense `d`, position `p ∈ {QB, RB}` over completed games in window:

```
raw_epa(d,p) = mean total EPA allowed to p per game
prior(p)     = league mean raw_epa
n(d,p)       = game count
shrunk       = (n * raw + k * prior) / (n + k)
```

Rank defenses by `shrunk` **descending** (higher allowed EPA = softer). Buckets identical to Tier 1 (`soft` 1–7, `neutral` 8–25, `tough` 26–32).

## API

- `GET /api/v1/nfl/strength-of-schedule/tier2?position=QB|RB&window=l4|l8|season&startWeek=&endWeek=&season=`
  - Grid cells: `shrunkEpa`, `rank`, `softness`, `softnessScore` (parallel to Tier 1 `shrunkAfpa`)
- `GET /api/v1/nfl/strength-of-schedule/tier2/opportunity?position=QB|RB&window=&week=&leagueId=&season=`
  - Extra fields per player: `gameScriptDelta`, `adjustedSoftness`, `minOffenseSnapPct`
  - Response notes: `snapFiltered`, `gameScriptApplied`, `softnessMetric: "epa_allowed"`

Tier 1 opportunity and grid endpoints are unchanged.

## Errors

- Invalid position on tier2 → 400
- Snap fetch fail on tier2 opportunity → 200 with `snapFiltered: false` and Tier-1-style unfiltered usage (documented fallback for Railway)
- Odds fail → `gameScriptApplied: false`
- nflverse grid fail → existing stale snapshot behavior

## Testing

- Snap filter: backup RB excluded from denominator changes share
- Game script: high implied boosts opportunity vs neutral
- EPA rank: known fixture ordering + shrink n=0
- API: tier2 shape, QB-only 400 on WR
- Web: tier2 toggle fetches `/tier2` URLs
