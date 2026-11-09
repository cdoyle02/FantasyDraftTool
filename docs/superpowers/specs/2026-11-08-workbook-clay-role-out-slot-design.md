# Workbook Out/Slot via Clay role (P0.5)

**Date:** 2026-11-08  
**Status:** Approved (design)  
**Parent:** [Workbook Net Matchups](./2026-11-08-workbook-net-matchups-design.md) · [Alignment source research](./2026-11-08-workbook-alignment-source-research.md)

## Goal

Fill Workbook `outWr` / `slotWr` Net columns cheaply and quickly using Mike Clay’s free weekly WR/CB Cheat Sheet PDF for **player role** (slot-primary vs outside-primary), then aggregate nflverse WR week stats into OFF/DEF/Net — without FTN Participation or FantasyPros.

## Decisions

| Topic | Choice |
|-------|--------|
| Source | ESPN CDN Clay PDF: `https://g.espncdn.com/s/ffldraftkit/26/NFL26_CS_WRCB.pdf` (season folder `26` = 2026; update year with season) |
| Cost / auth | Free; no login; no FantasyPros |
| Fidelity | **Role-based**, not play-level `skp_pos`. UI label: **Out/Slot (Clay role)** |
| Parse fields | Team, receiver name, Pos (`L`/`S`/`R`), LWR%, Slot%, RWR% |
| Classify | Slot-primary if `Slot% ≥ 45`; else if Pos=`S`; else outside-primary. WR only |
| Coverage | Clay lists ~3 WRs/team; unlisted WRs stay in ALL WR only (not forced into Out/Slot) |
| Bye / missing week | Reuse **last known** Clay role for that player (season cache); if never seen → omit from Out/Slot |
| Team abbrevs | Map Clay → app: `ARZ→ARI`, `BLT→BAL`, `CLV→CLE`, `HST→HOU` (plus existing SoS aliases) |
| Name join | Prefer exact `player_display_name`; fallback normalized (case, punctuation). Unmatched Clay rows logged; no silent invent |
| OFF | Per team-week: sum nflverse WR fantasy/targets/yards/TDs for slot-primary vs outside-primary WRs on that offense |
| DEF | Same sums for WRs whose **opponent** that week is the defense |
| Net | Existing `mean_net(OFF, OppDEF)` into board `outWr` / `slotWr` |
| Failure | PDF/parse fail → keep `null` + `insufficient_alignment_sample` (or `clay_unavailable`); do not guess |
| Cache | Process TTL aligned with workbook (~6h); packaged snapshot may include last Clay roles |
| Attribution | Footer notes Clay PDF for roles; numbers still ours from nflverse |
| Non-goals | Clay CB shadow cheatsheet UI (separate later); FTN wire-up; play-level alignment; scraping Majesstik |

## Architecture

```
draft_api/workbook/
  clay_pdf.py       # download + parse WR rows → ClayWrRole
  roles.py          # classify + last-known cache merge
  nflverse.py       # when building out_wr/slot_wr positional rates, join roles
  service.py        # board already exposes outWr/slotWr; attribution string update
```

Flow: refresh/load workbook dataset → fetch/parse Clay (or use cache) → map player→role → aggregate Out/Slot OFF/DEF from stats_player_week → existing Net path.

## Verification notes (2026-11-08)

- Week 9 PDF: 75 WR rows, 25 teams (byes). Known slot WRs classify correctly (Shakir, Downs, McConkey, Amon-Ra, Flowers).
- ~3 Pos vs Slot% conflicts; Slot%≥45 rule preferred.
- nflverse name join exact for common samples; Clay team codes need alias map.

## Testing

- Fixture: committed snippet/text of one Clay PDF page (or extracted rows JSON) — no network in CI.
- Classifier unit tests (threshold, Pos=S, conflicts).
- Alias map tests.
- Integration: fixture roles + tiny stats weeks → non-null `outWr`/`slotWr` nets.
- Failure: bad PDF bytes → null Out/Slot, board still returns ALL WR.

## Success

Workbook Out/Slot cells populate for teams with Clay-listed WRs under L4/PPR; UI shows Clay-role attribution; bye weeks don’t wipe roles; CI stays offline-safe.
