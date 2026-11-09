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

## Tier 1 (shrunk aFPA)

Rolling defensive allowance with empirical-Bayes shrink toward the league mean:

```
shrunk = (n * raw_afpa + k * prior) / (n + k)
```

- Default pseudo-count **`k = 4`** (`shrinkK` in API responses).
- Rating window: **`l4`** (last 4 completed weeks), **`l8`** (default), or **`season`** (week 1 through `ratedThroughWeek`).
- Softness buckets by defense rank (1 = softest): ranks **1–7** `soft`, **8–25** `neutral`, **26–32** `tough`.
- Linear scores: soft **1.0**, neutral **0.5**, tough **0.0** (for future opportunity = softness × usage).

Classic FPA/PAE endpoint is unchanged.

## Endpoints

`GET /api/v1/nfl/strength-of-schedule?position=RB&metric=fpa&startWeek=10&endWeek=17&season=2026`

`GET /api/v1/nfl/strength-of-schedule/tier1?position=RB&window=l8&startWeek=10&endWeek=17&season=2026`
