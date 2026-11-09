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

## Endpoint

`GET /api/v1/nfl/strength-of-schedule?position=RB&metric=fpa&startWeek=10&endWeek=17&season=2026`
