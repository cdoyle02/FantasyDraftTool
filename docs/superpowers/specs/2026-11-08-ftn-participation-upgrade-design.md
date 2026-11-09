# FTN Participation upgrade (play-level Out/Slot)

**Date:** 2026-11-08  
**Status:** Design gates only — **no paid wire** until sample schema + license are approved  
**Depends on:** [Alignment source research](./2026-11-08-workbook-alignment-source-research.md), [Clay role Out/Slot](./2026-11-08-workbook-clay-role-out-slot-design.md) (current primary), Workbook Net Matchups ([design](./2026-11-08-workbook-net-matchups-design.md))  
**Related:** SoS Clay splits stay role-based until this upgrade ships; [Tier 3 ensemble](./2026-11-08-advanced-sos-tier3-design.md) does **not** require FTN.

## Goal

Define the contract for upgrading Workbook (and optionally SoS) **Out / Slot WR** from Clay **role-based** aggregates to FTN Data **play-level Participation** (`skp_pos`) — without implementing network/auth against FTN until household license + a validated sample file exist.

## Current state

| Layer | Status |
|-------|--------|
| Clay weekly WR/CB PDF → slot/outside role → nflverse WR week OFF/DEF/Net | **Shipped** (Workbook + SoS `wrRole`) |
| `parse_alignment_csv` / `ALIGNMENT_COLUMN` hooks in workbook nflverse loader | Present; **unused for rates** while Clay is primary |
| Public nflverse FTN charting | **Insufficient** (no `skp_pos` / receiver alignment) |
| nflverse participation release | Postseason-only for FTN era — not in-season P0 |

## Hard gates (must pass before any paid wire)

1. **License / cost** — Confirm household use, whether derived snapshots may be committed privately, redistribution of derived Net rates in the app UI (not raw FTN rows). Prefer API Participation tier if CSV `$599` still excludes Participation (research note: API ~`$5k/yr` associates Participation).
2. **Sample schema** — Obtain a redacted or historical sample with `gid`, `pid`, `skp(1-5)`, `skp_pos(1-5)` (and ideally `nflverse_game_id` + `play_id`). Fixture lives under `apps/api/tests/workbook/fixtures/` — never commit live credentials.
3. **Join validation** — Prove crosswalk: do **not** assume `pid == play_id`. Prefer FTN-supplied nflverse ids; otherwise document a validated gid/pid map with measured match rate.
4. **Coding dictionary** — Lock `skp_pos` values: `SLT` → slot; confirm whether `WR` means outside/boundary; exclude `Y-TE` / `H-TE` / `HB` / `FB` from Slot WR counts (WR-only Slot rule unchanged).
5. **Refresh SLA** — Document post-game availability vs Clay PDF cadence; define stale fallback.

Until gates 1–4 pass: **Clay remains primary**. No FTN client, env keys, or live downloads in production paths.

## Locked product decisions (when gates pass)

| Topic | Choice |
|-------|--------|
| Normalize target | Existing `receiver_alignment`: `slot` \| `outside` \| `other` |
| Slot eligibility | **WR only** (TE/RB in slot excluded) |
| Insufficient sample | `null` rates + `insufficient_alignment_sample` (same as P0) |
| Dual-run with Clay | Compute both when FTN present; **FTN wins** for Out/Slot rates; UI label **"Out/Slot (play-level)"** vs **"Out/Slot (Clay role)"** |
| Missing FTN week | Fall back to Clay roles; set `alignmentSource: "clay_role"` |
| Secrets | `FTN_*` keys in platform env / local `.env` only — never tool args, never chat, never commit |
| Non-substitutes | Do **not** invent Out/Slot from `pass_location`, public FTN charting, or NGS |

## Architecture (proposed — implement only after gates)

```
apps/api/src/draft_api/workbook/
  ftn_participation.py   # NEW: parse sample/API → alignment events
  alignment.py           # keep normalize helpers
  nflverse.py            # prefer FTN alignment bags when non-empty; else Clay
  service.py             # attribution + alignmentSource field
```

Snapshot packaging: trimmed alignment events or pre-aggregated Out/Slot OFF/DEF — confirm license before committing derived blobs.

## Dual-run contract

```
if ftn_alignment_events for season/window:
  fill out_wr / slot_wr from play-level targets
  alignmentSource = "ftn_participation"
elif clay_roles:
  fill from Clay role × nflverse WR weeks
  alignmentSource = "clay_role"
else:
  null + insufficient_alignment_sample
  alignmentSource = "none"
```

Attribution string must name the active source. SoS `wrRole` filter continues to use Clay roles until a separate SoS play-level plan exists.

## Non-goals (this design)

- Paying for or wiring FTN without a sample
- Scraping Majesstik / FootClan
- Using public FTN charting as a silent Out/Slot substitute
- Replacing Clay CB shadow (separate wishlist)
- Changing Net Matchups formulas beyond Out/Slot fill source

## Success criteria (when implemented later)

- Fixture proves WR-only Slot counts and join match rate ≥ household threshold (lock number in impl plan)
- UI never claims play-level when Clay is active
- Clay path remains green if FTN credentials missing
- No secrets in git; CI uses fixtures only

## Open questions

1. Accept CSV-only Participation if FTN offers it later, or commit to API?  
2. May derived weekly Out/Slot aggregates be committed under private license, or must they stay runtime-only?  
3. Extend SoS Out/Slot to play-level in the same milestone, or Workbook-first?

## Implementation next step

Do **not** open an implementation plan until gates 1–4 are checked off in this doc (add a short “Gate log” section with dates). Then write `docs/superpowers/plans/2026-*-ftn-participation-upgrade.md`.
