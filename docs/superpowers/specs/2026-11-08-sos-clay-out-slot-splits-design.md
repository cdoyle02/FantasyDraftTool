# SoS Clay Out/Slot WR splits

**Date:** 2026-11-08  
**Status:** Approved (design); plan: [sos-clay-out-slot-splits](../plans/2026-11-08-sos-clay-out-slot-splits.md)  
**Depends on:** [Clay Workbook roles](./2026-11-08-workbook-clay-role-out-slot-design.md), SoS Tier 1–2

## Goal

Expose FootClan-style **Outside WR** vs **Slot WR** strength-of-schedule on the SoS tab using existing Clay role classification + nflverse WR week stats — without FTN Participation.

## Locked decisions

| Topic | Choice |
|-------|--------|
| Role source | Same Clay classify as Workbook (`Slot%≥45` else Pos=`S` else outside); reuse `workbook.roles` |
| API param | `wrRole=all\|outside\|slot` (default `all`) on Tier 1 + Tier 2 grid and opportunity routes when `position=WR` |
| Invalid combo | `wrRole` outside/slot with non-WR → 400 |
| Tier 2 metric | Filter WR `receiving_epa` rows to Clay-listed players matching role before DEF aggregation |
| Tier 1 metric | Filter WR `fantasy_points_ppr` the same way for shrunk aFPA |
| Unlisted WRs | No Clay role → **excluded** from Out/Slot denominators (same as Workbook) |
| `wrRole=all` | Unchanged current WR behavior (all WRs) |
| Role cache | Embed `clayRoles` on SoS packaged snapshot at refresh; resolve live Clay → sos snap → workbook snap |
| Opportunity | Only players with matching Clay role; softness from the role-specific defense index |
| UI | When position=WR: All \| Out (Clay) \| Slot (Clay) toggle; labels note Clay role |
| Non-goals | FTN play-level; Clay CB shadow; changing classic FPA/PAE CompletedGame path |

## Success

- Tier 2 WR + `wrRole=slot` ranks defenses by EPA allowed to Clay slot WRs only.
- Same for outside / Tier 1 aFPA.
- Offline: packaged `clayRoles` keeps splits working when PDF fetch fails.
- Tier 1 defaults and non-WR positions unchanged when `wrRole=all` or omitted.
