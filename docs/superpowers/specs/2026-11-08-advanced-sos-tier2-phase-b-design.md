# Advanced SoS — Tier 2 Phase B

**Date:** 2026-11-08  
**Status:** Approved (design); implementation: [Tier 2 Phase B plan](../plans/2026-11-08-advanced-sos-tier2-phase-b.md)  
**Depends on:** [Tier 2 Phase A](./2026-11-08-advanced-sos-tier2-design.md)

## Goal

Close Phase A Railway/offline gaps and extend the EPA Tier 2 surface to **WR and TE**, without Clay Out/Slot SoS splits (still deferred).

## Locked decisions

| Topic | Choice |
|-------|--------|
| Snap packaging | Embed trimmed `snapCounts` rows in `sos_{season}.json` on refresh; Tier 2 opportunity falls back live → packaged (same pattern as `usageStats`) |
| Snap trim | Keep `season`, `week`, `game_type`/`season_type`, `team`, `player`, `offense_pct` only |
| Usage EPA columns | Add `passing_epa`, `rushing_epa`, `receiving_epa` to `USAGE_STATS_FIELDS` so packaged opportunity/EPA works offline |
| Tier 2 positions | **QB, RB, WR, TE** — DST still 400 |
| WR/TE EPA | Per completed game: sum `receiving_epa` for WR or TE rows (`team` offense, `opponent_team` defense); same shrink + 7/18/7 buckets as QB/RB |
| Opportunity | Same Phase A formula; snap filter + game-script apply for all skill positions |
| UI | Tier 2 mode available for QB/RB/WR/TE (no auto-fallback to Tier 1 except DST) |
| Non-goals | WR1/Out/Slot SoS split, ridge PAE, ensemble, FootClan scrape, changing default view away from Tier 1 |

## API

- Existing `GET …/tier2` and `…/tier2/opportunity` accept `position=WR|TE` (in addition to QB|RB).
- Response may include `snapSource: "nflverse" | "snapshot" | "none"` when useful for debugging.

## Success

- Offline/stale SoS path can still `snapFiltered: true` when packaged snaps exist.
- Packaged `usageStats` includes EPA fields after refresh.
- WeekSosView Tier 2 works for WR/TE.
- Tier 1 routes and defaults unchanged.
