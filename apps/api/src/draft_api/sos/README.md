# Strength of schedule (SoS)

Household strength-of-schedule grid for QB / RB / WR / TE / DST.

## Metrics

- **FPA** — mean fantasy points a unit allowed to the position per completed game. Rank 1 allows the most (easiest). Skill spots use full PPR; **DST** uses ESPN-style D/ST scoring from nflverse team stats (sack/INT/FR/TD/safety/block + points-allowed brackets).
- **PAE** — schedule-adjusted: for each game, points allowed minus that offense’s leave-one-out average at the position. Rank 1 is softest relative to opponents faced.

Week cells show the **opponent’s rank vs the position** (1 easiest … 32 hardest). For DST that means how many D/ST fantasy points the opposing *offense* tends to allow. **Opp avg** averages those raw FPA/PAE values over the selected week window (byes excluded). Numbers will not match FootClan.

## Refresh snapshot

Live API downloads nflverse into a 6-hour memory cache. On failure it serves the packaged snapshot with `stale: true`.

```bash
# From repo root (writes apps/api/src/draft_api/data/sos_2026.json)
uv run python -m draft_api.sos.refresh --season 2026
```

Commit the updated JSON and redeploy the API so Railway’s fallback stays current.

The snapshot also embeds trimmed `usageStats` rows (from `stats_player_week`) so Tier 1 **opportunity** can still compute usage shares when the live stats download fails. If neither live nor packaged usage rows are available, responses set `usageUnavailable: true` (empty `players`).

## Tier 1 (shrunk aFPA)

Rolling defensive allowance with empirical-Bayes shrink toward the league mean:

```
shrunk = (n * raw_afpa + k * prior) / (n + k)
```

- Default pseudo-count **`k = 4`** (`shrinkK` in API responses).
- Rating window: **`l4`** (last 4 completed weeks), **`l8`** (default), or **`season`** (week 1 through `ratedThroughWeek`).
- Softness buckets by defense rank (1 = softest): ranks **1–7** `soft`, **8–25** `neutral`, **26–32** `tough`.
- Linear scores: soft **1.0**, neutral **0.5**, tough **0.0**.

### Opportunity

`opportunity = softness_score × usage_share` for skill positions (QB/RB/WR/TE; **DST excluded**).

| Position | Usage share (window mean of weekly ratios) |
|----------|---------------------------------------------|
| RB | `carries / team carries` |
| WR / TE | `targets / team targets` (same position group) |
| QB | `1.0` for team passing-yards leader in window; backups → `null` share |

Offline Spearman backtest: `draft_api.sos.backtest.run_tier1_backtest` (see `apps/api/tests/sos/fixtures/tier1_backtest_summary.json`).

Classic FPA/PAE endpoint is unchanged.

## Tier 2 Phase A (EPA + snap + game script)

**Positions:** QB and RB only (grid + opportunity).

### Snap-filtered usage

- Source: nflverse `snap_counts` (`offense_pct`).
- Default **`minOffenseSnapPct = 0.20`** — player-weeks below this are excluded from team carry/target denominators (Tier 1 opportunity unchanged when snap data is not used).
- API fields: `snapFiltered`, `minOffenseSnapPct` on Tier 2 opportunity.

### Game-script adjustment

When Vegas lines are available (`week_odds`):

```
delta = clamp((teamImplied - 22) / 40, -0.15, +0.15)
adjustedSoftness = clamp(softnessScore + delta, 0, 1)
opportunity = adjustedSoftness × usageShare
```

Response: `gameScriptApplied`, per-player `gameScriptDelta`, `adjustedSoftness`, optional `teamImplied`.

### EPA allowed (shrunk)

Per defense, mean **passing EPA allowed** (QB) or **rushing EPA allowed** (RB) per game in the rating window, with the same shrink formula and softness buckets as Tier 1 aFPA. Grid cells expose `shrunkEpa` instead of `shrunkAfpa`; `softnessMetric: "epa_allowed"`.

## Endpoints

`GET /api/v1/nfl/strength-of-schedule?position=RB&metric=fpa&startWeek=10&endWeek=17&season=2026`

`GET /api/v1/nfl/strength-of-schedule/tier1?position=RB&window=l8&startWeek=10&endWeek=17&season=2026`

`GET /api/v1/nfl/strength-of-schedule/tier1/opportunity?position=RB&window=l8&week=10&season=2026` — nflverse players sorted by `opportunity` desc. With `leagueId` (household league from `espn_leagues.json`), returns ESPN roster rows joined by normalized name+team (`joinStatus`, `joinStats`); ESPN failures set `overlayError: espn_unavailable` and empty `players`.

`GET /api/v1/nfl/strength-of-schedule/tier2?position=QB|RB&window=l8&startWeek=10&endWeek=17&season=2026` — EPA-allowed grid (`shrunkEpa`).

`GET /api/v1/nfl/strength-of-schedule/tier2/opportunity?position=QB|RB&window=l8&week=10&season=2026` — snap-filtered usage × game-script-adjusted EPA softness; same optional `leagueId` overlay as Tier 1. Stats download failures fall back to packaged `usageStats`; if that is also empty, `usageUnavailable: true`.
