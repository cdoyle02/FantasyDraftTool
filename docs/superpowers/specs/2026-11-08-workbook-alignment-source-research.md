# Workbook WR Alignment Source Research

**Date:** 2026-11-08  
**Task:** 5.5, FantasyDraftTool Workbook P0  
**Decision (updated 2026-11-08):** No free **play-level** source. **P0.5 ships role-based Out/Slot** from the free weekly Mike Clay WR/CB Cheat Sheet PDF — see [clay-role-out-slot design](./2026-11-08-workbook-clay-role-out-slot-design.md). FTN Participation remains the deferred full-fidelity upgrade.

## Recommendation

Ranked recommendation:

1. **Mike Clay weekly WR/CB PDF (role-based) — P0.5** - Free ESPN CDN cheat sheet with LWR/Slot/RWR %. Fast household path; not play-level. Spec: [clay-role-out-slot](./2026-11-08-workbook-clay-role-out-slot-design.md).
2. **FTN Data Participation Feed, direct paid API/package** - Best full-fidelity source (`skp_pos`). Note: **$599 CSV tier does not include Participation**; API (~$5k/yr) does.
3. **Household-maintained supplemental CSV** - Normalized to `receiver_alignment` if a licensed/play-level file appears.
4. **nflverse participation release** - Postseason-only for FTN era; not in-season P0.
5. **SIS / PFF / RotoWire / Fantasy Points Data Suite** - Aggregate or paid; secondary to Clay for speed.
6. **nflverse FTN charting / NGS / pass_location** - Not sufficient for exact Out/Slot; do not use pass_location as a silent substitute.

## Ranked Options

### 1. FTN Data Participation Feed, direct paid source

**Availability:** Current 2025-2026 data is available commercially from FTN. FTN's pricing page lists API access with advanced charting and player participation data for all skill positions.  
**Cost/license:** Paid. As of this research, FTN lists CSV access at $599/year and API access at $5,000/year; the page specifically associates player participation data with API access. Redistribution and derived-public-output rights must be confirmed in the subscription terms.  
**Refresh cadence:** FTN indicates post-game/approval availability; Exa found current-source summaries around roughly 24 hours after games, but this must be confirmed in the contract/sample docs before depending on it.  
**Columns/signal:** FTN's catalog documents `gid`, `pid`, `form`, `form_align`, `qb`, `qb_role`, `skp(1-5)`, `skp_pos(1-5)`, `skp_role(1-5)`, `mot(1-5)`, `def(1-5)`, `def_pos(1-5)`, and `cushion(1-5)`. `skp_pos` values include `WR`, `SLT`, `Y-TE`, `H-TE`, `HB`, and `FB`.  
**Join keys to nflverse PBP:** Direct FTN keys are `gid` + `pid`. Production wiring should require either FTN-supplied `nflverse_game_id` + `nflverse_play_id` or a validated crosswalk. Do not assume `pid == play_id`.  
**WR-only feasibility:** Strong. Unpivot `skp(1-5)`/`skp_pos(1-5)`, join the target player on each pass play, keep only target rows where the player's football position is WR, and classify `SLT` as slot and `WR` as outside after confirming FTN's exact coding.  
**Implementation step:** Add a paid-source loader only after receiving a schema sample, terms approval, and a non-secret delivery path. Normalize it to the existing `ALIGNMENT_COLUMN = "receiver_alignment"` contract.

### 2. Household-maintained supplemental CSV

**Availability:** Available only if the household creates or acquires a file. No authoritative free 2025-2026 public supplemental CSV was found.  
**Cost/license:** Controlled by the file source. Must be documented before commit. Do not scrape Majesstik's Google Sheet or any other sheet without explicit permission.  
**Refresh cadence:** Manual or source-specific. Must be stated in the CSV README/metadata.  
**Columns/signal:** Recommended minimum schema: `nflverse_game_id`, `nflverse_play_id`, `receiver_player_id` or target player ID where available, and `receiver_alignment` with values the current classifier can map to `slot` or `outside`.  
**Join keys to nflverse PBP:** Preferred join is `nflverse_game_id` + `nflverse_play_id`, matching the current `parse_alignment_csv` defensive hook.  
**WR-only feasibility:** Good if the file has player-level target alignment; not feasible if it only has play-level formation or pass location.  
**Implementation step:** Keep the current defensive parser. If a CSV is created later, add a fixture test that proves the file activates Out/Slot without changing the Workbook calculator.

### 3. nflverse participation release

**Availability:** Free through nflverse, but participation from 2023 onward is FTN-supplied after all postseason games are complete and does not update during the season. That makes it unsuitable for current 2026 P0 weekly usage.  
**Cost/license:** Free under CC BY-SA 4.0 with attribution to FTN Data via nflverse for 2023 onward and NFL Next Gen Stats via nflverse for earlier seasons.  
**Refresh cadence:** Not in-season for participation. The nflverse schedule explicitly says the participation release does not update during the season.  
**Columns/signal:** The public dictionary documents `nflverse_game_id`, `play_id`, formation/personnel, `players_on_play`, `offense_players`, `defense_players`, route, coverage, and related columns. It does not document raw FTN `skp_pos(1-5)`.  
**Join keys to nflverse PBP:** Strong: `nflverse_game_id` + `play_id`, and `load_participation(..., include_pbp = TRUE)` can join PBP.  
**WR-only feasibility:** Partial for historical route/participation research, but insufficient for exact current-season Out/Slot WR targets because raw slot/outside skill-player alignment is not documented and current-season data is unavailable.  
**Implementation step:** Do not wire for P0. Revisit only if a released season's actual columns include a stable player-level alignment signal.

### 4. nflverse FTN charting/open data

**Availability:** Free public release from 2022 onward, including current 2026 charting as games are processed.  
**Cost/license:** Free via nflverse under CC BY-SA 4.0 with FTN attribution.  
**Refresh cadence:** `nflreadr` documents FTN charting updates at 00, 06, 12, and 18 UTC during the season, with actual availability dependent on FTN. The loader docs say data is charted within roughly 48 hours.  
**Columns/signal:** Official dictionary has 29 fields, including FTN/nflverse game and play IDs, hash, QB location, backfield/box counts, no-huddle, motion, play action, screen, RPO, trick play, catchable/contested/drop flags, blitzers, pass rushers, and `date_pulled`. It has no per-target `receiver_alignment`, no `skp_pos`, and no five skill-player slots.  
**Join keys to nflverse PBP:** Excellent: `nflverse_game_id` + `nflverse_play_id`.  
**WR-only feasibility:** No for exact Out/Slot. It can enrich play context but cannot identify whether the target was slot or outside.  
**Implementation step:** Keep as optional context only. The existing defensive `parse_alignment_csv` correctly returns no alignment when the column is absent.

### 5. NFL Next Gen Stats via nflverse

**Availability:** Free player-level weekly NGS from 2016 onward, including current-season nightly updates subject to NGS availability and minimum thresholds.  
**Cost/license:** Free through nflverse data access; underlying NFL NGS licensing is separate and not a public per-play feed for this task.  
**Refresh cadence:** Nightly during the season for player-level weekly stats.  
**Columns/signal:** Weekly player aggregates include player/team/week identifiers, average cushion, separation, air distance, targets, receptions, yards, touchdowns, and related stats. `avg_cushion` is measured at snap, but it is not slot/outside alignment.  
**Join keys to nflverse PBP:** Weekly only: `season`, `week`, and `player_gsis_id`; no documented `game_id` + `play_id` per-target join.  
**WR-only feasibility:** No for exact Out/Slot. It can filter WRs and provide context, but cannot split target rows by alignment.  
**Implementation step:** Do not wire for Out/Slot.

### 6. Sports Info Solutions / PFF paid data

**Availability:** Current paid products exist, but public docs do not provide a confirmed per-play nflverse-compatible target-alignment export. SIS advertises raw football data and participation data; PFF's developer docs require PFF Pro and expose aggregate slot receiving fields in public references.  
**Cost/license:** Paid subscriptions or enterprise/API contracts. Redistribution and internal use terms must be reviewed.  
**Refresh cadence:** Vendor-specific; no public SLA found that can be committed to P0.  
**Columns/signal:** PFF aggregate references include fields like `slot_targets`, `slot_routes`, `slot_pass_plays`, and slot receiving metrics. SIS publicly describes raw data and participation data, but not a stable public schema for per-target slot/outside.  
**Join keys to nflverse PBP:** Unconfirmed. Any use requires sample exports and a game/play/player ID crosswalk.  
**WR-only feasibility:** Plausible after vendor confirmation, but not wireable now. Aggregate slot fields do not satisfy the current per-target join design.  
**Implementation step:** Treat as backup commercial options if FTN is not acceptable.

## Decision

P0 should ship with the existing null-safe alignment path. No code hook is added in this task because no free, current-season, full-fidelity source exists now.

Deferred recommended source: **FTN Data Participation Feed via paid API/package**, normalized to a local/snapshot-safe supplemental CSV with `receiver_alignment` once licensing, sample schema, and join validation are complete.

Acceptance criteria before wiring:

- Confirm access terms allow household use and committed derived snapshots, if any.
- Confirm exact alignment values and whether `WR` means outside/boundary in FTN's feed.
- Confirm join keys to nflverse PBP on a multi-game sample, including penalties/no-plays and duplicate IDs.
- Add a fixture test proving WR slot/outside rows are counted and TE/RB slot rows are excluded.
- Keep pass-location approximations out of the UI unless a future decision record explicitly accepts degraded fidelity and labels it.

## Sources Consulted

- FTN NFL Data Catalog: https://ftnfantasy.com/ftn-data-nfl-catalog
- FTN Data pricing: https://www.ftndata.com/pricing
- nflreadr FTN charting loader: https://nflreadr.nflverse.com/reference/load_ftn_charting.html
- nflreadr FTN charting dictionary: https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html
- nflreadr participation loader: https://nflreadr.nflverse.com/reference/load_participation.html
- nflreadr participation dictionary: https://nflreadr.nflverse.com/articles/dictionary_participation.html
- nflreadr data schedule: https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html
- nflreadr Next Gen Stats dictionary: https://nflreadr.nflverse.com/articles/dictionary_nextgen_stats.html
- PFF Developer API: https://developer.pff.com/
- Sports Info Solutions football products: https://www.sportsinfosolutions.com/football/
