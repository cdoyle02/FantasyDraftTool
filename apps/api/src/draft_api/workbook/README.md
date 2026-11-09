# Workbook metric SSOT

This is the source of truth for every number the Workbook Net Matchups board,
feeders, and explain panel compute. It mirrors `draft_api/sos/README.md`'s
role for the SoS tab: when the service layer's output and this file
disagree, this README is authoritative and the service should be fixed.

**Attribution:** methodology is inspired by Majesstik / OWS "#TheWorkbook"
(see the design spec), but every number here is computed by FantasyDraftTool
from nflverse + our own odds — we never scrape or republish their sheet. The
API response always carries this as the `attribution` field.

## Data sources

| Input | Source | Notes |
|---|---|---|
| Play-by-play | nflverse `play_by_play_{season}.csv.gz` | Drives, DSR, PROE, explosives, Out/Slot join |
| Weekly player stats | nflverse `stats_player_week_{season}.csv.gz` | QB/ALL WR/TE/RB OFF-produced and DEF-allowed rate sums |
| Schedule | nflverse `games.csv` | Team-week opponent map (`schedule`) + home/away/kickoff (`games`, this task) |
| Alignment (Out/Slot) | nflverse `ftn_charting_{season}.csv` | **Deferred** — the public release has no per-target alignment column (see below) |
| Vegas | `week_odds` / `OddsProvider` (`GameLine`) | **Optional** — passed in by the caller; `null` implied points if unavailable |

### nflverse download URLs (code constants)

These are the live release URLs the loader fetches (`workbook/nflverse.py` unless noted). Keep this table aligned with the constants when nflverse renames an asset.

| Asset | Constant (module) | URL template |
|---|---|---|
| Play-by-play | `PBP_URL` (`workbook/nflverse.py`) | `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz` |
| Weekly player stats | `STATS_URL` (`sos/nflverse.py`, shared) | `https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv.gz` |
| Schedule | `SCHEDULES_URL` (`sos/nflverse.py`, shared) | `https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv` |
| FTN charting | `FTN_CHARTING_URL` (`workbook/nflverse.py`) | `https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_{season}.csv` (plain `.csv`, not `.csv.gz`) |

Packaged fallback: `draft_api/data/workbook_{season}.json` (see **Cache / stale / snapshot**). Refresh with `uv run python -m draft_api.workbook.refresh --season {season}` from repo root.

## Rolling window

`resolve_stat_weeks(mode, rated_through_week, custom_start, custom_end)`
(`workbook/calculate.py`):

- `ratedThroughWeek = max(0, min(week - 1, 18))` — the board is for a
  not-yet-played week, so stats are rated through the week before it.
- **l4** (default): the 4 completed weeks ending at `ratedThroughWeek`.
- **season**: every completed week, `1..ratedThroughWeek`.
- **custom**: an inclusive `[start, end]` range clipped to `1..18`.

Only weeks that actually have data for a given team/group contribute to that
metric's game count — missing weeks (bye, early season, no PBP row) are
skipped rather than zero-filled.

## Net math (universal convention)

Every "Net" number on the board is:

```
Net = mean(offense's own rate, opponent's allowed rate)
```

i.e. `mean_net(off, opp_def)` (`workbook/calculate.mean_net`) applied
per-metric. A missing leg (no sample) makes the Net `null` rather than a
half-computed value — never fabricate the missing side.

- **Comb Net DSR** = mean of both teams' own Net DSR for that game
  (`comb_net_dsr`).
- **Net DSR Diff** = team Net DSR − opponent Net DSR (`net_dsr_diff`).

## P0 Net Matchups board columns

Each `games[].rows[]` entry (`build_matchups_response`) is one team in a scheduled game. P0 UI headline cells (`WeekWorkbookView`) and explain-on-click targets:

| UI label | JSON path | Explain `metric` | Notes |
|---|---|---|---|
| Vegas Impl | `gameEnvironment.vegasImpliedPoints` | — | Display-only; not a Net average |
| Net DSR | `gameEnvironment.netDsr` | `dsr` | `mean_net` of team OFF DSR + opponent DEF allowed DSR |
| Comb DSR | `gameEnvironment.combNetDsr` | — | Mean of both teams' `netDsr` for the game |
| DSR Diff | `gameEnvironment.netDsrDiff` | — | Team `netDsr` − opponent `netDsr` |
| QB | `qb.fpGTot` | `qb_fp` | Full positional block available via API; board shows headline only |
| ALL WR | `allWr.fpG` | `wr_fp` | |
| Out WR | `outWr.fpG` | `out_wr_fp` | `reason: clay_unavailable` when Clay role sample is thin |
| Slot WR | `slotWr.fpG` | `slot_wr_fp` | Same gating as Out WR |
| TE | `te.fpG` | `te_fp` | |
| RB | `rb.fpGTot` | `rb_fp` | |

Additional `gameEnvironment` Net env rates (`netProe`, `netPassPlays`, `netEpaPass`, `netXplsvPass`, `netRunPlays`, `netEpaRun`, `netXplsvRun`) are computed for P0 but not shown as board columns yet.

## Game Environment

Built by `build_game_environment_net` from two legs:

| Field | Definition |
|---|---|
| `vegasImpliedPoints` | From the caller-supplied `GameLine` (favorite/underdog implied split via `implied_team_totals`); `null` when no odds were supplied for this game |
| `netDsr` | `mean_net(team's own DSR, opponent's DSR allowed)` — see DSR below |
| `combNetDsr` | Mean of both teams' `netDsr` |
| `netDsrDiff` | Team `netDsr` − opponent `netDsr` |
| `netProe`, `netPassPlays`, `netEpaPass`, `netXplsvPass`, `netRunPlays`, `netEpaRun`, `netXplsvRun` | `mean_net` of the team's OFF `TeamRateSlice` and the opponent's DEF `TeamRateSlice` for the same field |

### DSR (drive success rate)

Share of drives ending in a first down or touchdown; QB-kneel-only drives are
excluded entirely (not counted as a failure) — see `drive_success_rate` and
the PBP loader's drive-state logic.

`DriveOutcome` only tags the **offensive** team per drive. The
defense-allowed leg (`_defense_allowed_dsr` in `service.py`) is derived by
looking up each week's opponent in the season `schedule` and pooling that
opponent's drives for the week — there is no separate "defense" drive
record.

### PROE / pass plays / EPA / explosives

Computed once per team-week as an OFF or DEF `TeamRateSlice` directly in the
nflverse loader (`parse_play_by_play`): OFF when the team has the ball
(`posteam`), DEF when it doesn't (`defteam`). The service layer only
averages existing slices over the window (`build_team_env_rates`) — no
schedule join needed here, unlike DSR.

- **PROE** = mean(`is_pass` as 0/1 − `xpass`) × 100, over plays with a known
  `xpass`. Plays without `xpass` are excluded from the sample, not treated as
  0.
- **Explosive pass** = gain > 15 yards; **explosive run** = gain > 10 yards
  (OWS "By The Numbers" thresholds).

## Positional Net blocks (QB / ALL WR / Out WR / Slot WR / TE / RB)

Each block is `build_positional_net(offMetrics, defMetrics)` — i.e.
`mean_net` applied key-by-key to two per-game metric dicts. A key present on
only one side still appears, net to `null`.

Per-game metrics are built from the raw `PositionalWeekRate` sums over the
window (`_sum_group_rates` + `_rate_metrics` in `service.py`), using the same
`fantasy.py` scoring formulas as everywhere else in the app (not nflverse's
precomputed `fantasy_points_ppr`), so the PPR / Half-PPR toggle is always
honored:

| Group | Fields | Formula notes |
|---|---|---|
| **QB** | `fpGTot`, `fpGPass`, `fpGRun`, `ydsG`, `passTdG` | `fpGPass` = `passing_points(yards, tds)` / games (no INT data in the weekly-stats feed yet — `ints=0`); `fpGRun` = `rushing_points(yards, tds)` / games; `fpGTot` = their sum |
| **ALL WR / Out WR / Slot WR / TE** | `fpG`, `tarG`, `tarPct`, `ydG`, `tdG` | `fpG` = `receiving_points(receptions, yards, tds, scoring)` / games |
| **RB** | `fpGTot`, `fpRec`, `fpRun`, `tarG`, `tarPct`, `recYdG`, `recTdG`, `attG`, `rushYdG`, `rushTdG` | `fpGTot` = `fpRec` + `fpRun` |

`tarPct` = group targets ÷ team's total WR+TE+RB targets for the same window
(`_team_total_targets`) — QB has no `tarPct`. Out WR / Slot WR targets are a
subset of ALL WR and are **not** double-counted in that denominator.

### Out / Slot WR — Mike Clay role method (P0.5)

**Source:** ESPN CDN Mike Clay WR/CB cheat sheet PDF
(`https://g.espncdn.com/s/ffldraftkit/{yy}/NFL{yy}_CS_WRCB.pdf`), parsed in
`workbook/clay_pdf.py`. **Role:** slot-primary when `Slot% ≥ 45`, else when Clay
`Pos=S`, else outside-primary (`workbook/roles.py`). Team codes `ARZ→ARI`,
`BLT→BAL`, `CLV→CLE`, `HST→HOU` before `normalize_team`.

**Join:** `normalize_player_name` on Clay names ↔ nflverse
`player_display_name`. Unlisted WRs stay in ALL WR only — never forced into
Out/Slot.

**Aggregate:** `aggregate_out_slot_from_stats` sums receiving targets/yards/TDs
and PPR fantasy points from `stats_player_week` into `out_wr` / `slot_wr`
OFF (producing team-week) and DEF (allowed on opponent-week) buckets.

**Bye / PDF miss:** `load_workbook_dataset` merges the fresh Clay index with
`merge_last_known` against `WorkbookDataset.clay_roles` from the prior refresh
(packaged snapshot `clayRoles` field). If the PDF fails, logged warning + last
known roles; if a player was never seen, omit from Out/Slot.

Rather than show a Net built on a near-zero sample, the service layer requires
**at least `_MIN_CLAY_SAMPLE_GAMES` (currently 1) team-weeks of both OFF and
DEF** in the window. Below that:

```json
{ "fpG": null, "reason": "clay_unavailable" }
```

Public nflverse `ftn_charting` still has no per-target alignment column; the
legacy `parse_alignment_csv` path remains for a future supplemental feed but is
not the primary Out/Slot source.

## Game list, kickoff, and slate filter

`WorkbookDataset.games` (`ScheduledGame`: `week`, `home`, `away`, `kickoff`)
is parsed from the same `games.csv` schedule download as `schedule`, but
keeps the home/away direction and kickoff time that the symmetric
`schedule` map intentionally drops. `kickoff` is a UTC ISO8601 string parsed
from nflverse's `gameday` (date) + `gametime` (local **Eastern** time per the
nflverse schedules dictionary); when either column is missing or unparsable
(e.g. the minimal CSV fixtures used in tests), `kickoff` is `null` for that
game.

- **`slate=all`** — every game scheduled for the requested week.
- **`slate=main`** — only games where `is_main_slate` is `True`: kickoff
  falls on **Sunday** (weekday `== 6`) before **7pm America/Chicago**
  (`kickoff_hour_local < 19`). This matches the design spec's "Sunday early +
  late windows only" and excludes Thu/Fri/Sat/Sun-night/Mon games.
- A `null` kickoff (schedule row without `gameday`/`gametime`, e.g. the
  packaged snapshot before a live refresh fills it in) is **never** promoted
  into `main` — it only shows up under `slate=all`. Adjust this fallback if
  the household slate definition needs it.

## Vegas implied points

`build_matchups_response(..., odds_games=...)` takes an **optional**
sequence of `GameLine` (the same type `week_odds` already returns). When a
game's `(home, away)` pair matches a supplied `GameLine`, implied points are
split via `implied_team_totals(total, spread)` and assigned to the home/away
side matching `favorite_team`. When `odds_games` is omitted, doesn't cover a
game, or the favorite doesn't match either scheduled team,
`vegasImpliedPoints` is `null` — **the board never fails because odds are
unavailable.** Task 8 is expected to wire the real `OddsProvider` (same one
`/api/v1/nfl/week-odds` uses) into this parameter.

## Cache / stale / snapshot (mirrors `sos/service.py`)

- `resolve_dataset(season)` prefers a 6-hour in-process `TtlCache` of the
  live nflverse dataset (`source: "nflverse"`, `stale: false`).
- On loader failure (`WorkbookNflverseError`), it falls back to the packaged
  snapshot (`source: "snapshot"`, `stale: true`) rather than failing the
  request.
- If the snapshot is also missing/invalid, the error propagates (503 at the
  route layer, Task 8).
- Test hooks: `set_workbook_dataset_override` (bypasses download + snapshot
  entirely — `source: "fixture"`), `set_workbook_http_get`, `clear_workbook_cache`.

## Feeders

`build_feeder_response(group=...)` returns one row per team with `off`,
`def`, and `net` for a single headline metric:

| `group` | Headline metric |
|---|---|
| `dsr` | Drive success rate |
| `qb` | `fpGTot` |
| `wr` | `fpG` (`all_wr` bucket) |
| `te` | `fpG` |
| `rb` | `fpGTot` |
| `targets` / `yards` / `tds` | Per-game raw volume (`targets`, `rec_yards`, `rec_tds`), pooled across WR+TE+RB |

Out WR / Slot WR drill-down and the full positional metric set are reachable
via `explain`, not the feeder table, in P0.

## P2 supporting tabs (API)

### Time of possession (TOP)

`GET /api/v1/nfl/workbook/top` (`build_top_response`) — rolling window matches
matchups (`l4` | `season` | `custom`, rated through `week - 1`).

- **Primary (when PBP drive seconds are wired):** `method: "pbp_drive"` —
  mean per-game share `team_drive_seconds / (team + opponent drive seconds)`.
- **Fallback (current nflverse loader):** `method: "plays_share_proxy"` —
  mean per-game `team_off_plays / (team_off_plays + opponent_off_plays)` using
  `TeamRateSlice.pass_plays + run_plays` from PBP aggregation. Labeled in API;
  upgrade path is real `drive_time_of_possession` in PBP (see
  `workbook/top.py`).

### Pace

`GET /api/v1/nfl/workbook/pace` — offensive plays per game and pass/run share
from countable PBP snaps (`pass_attempt` + `rush_attempt`, kneels already
dropped at parse; optional `play_type` kneel/spike/no_play excluded in
`pace.py` when present on test fixtures).

### Injuries

`GET /api/v1/nfl/workbook/injuries?leagueId=` — ESPN `mRoster` injury fields
(`injuryStatus`, `injuryBodyPart`, practice hints). Sorted by team then severity
(Out > Doubtful > Questionable > Probable). On ESPN failure: HTTP 200,
`injuries: []`, `warnings: ["injuries_unavailable"]`, `source: "espn"`.

### Positional matrices

`GET /api/v1/nfl/workbook/matrices/{group}?metric=` — OFF / DEF / Net columns
with **league-relative tertile tiers** for the selected window (not absolute FP
thresholds). Tier cut: rank `n` teams with data; top `ceil(n/3)` → `top`, next
`ceil(n/3)` → `mid`, remainder → `bottom`. Metrics: `fp_per_game` (positional
feeder headline), `targets_per_game` / `yards_per_game` / `tds_per_game`
(volume feeders), `dsr` (group `dsr` only).

## Explain

`build_explain_response(team, week, metric, ...)` returns the same `off` /
`def` / `net` triple that feeds one matchups-board cell, so a UI explain
panel's numbers always reconcile with the board (`net == off/def
mean_net(...)`, verified in `test_service.py`). `metric` is one of `dsr`,
`qb_fp`, `wr_fp`, `te_fp`, `rb_fp`, `out_wr_fp`, `slot_wr_fp`. `opponent` is
looked up from `schedule[week][team]`; if the team has a bye that week, `def`
and `net` are `null` and only `off` is returned.

## Known P0 gaps (tracked, not silently guessed)

- **Out/Slot alignment** — see above; always `null` against the current
  public nflverse release until a real source is wired.
- **QB Sack%** — not in the metric catalog output yet; the weekly-stats feed
  this loader reads has no sacks-taken column. Add it once a sacks source is
  wired (nflverse PBP has sack plays; this would need its own aggregation).
- **QB interceptions** — `passing_points` defaults `ints=0` for the same
  reason (no INT column in `stats_player_week`). Fantasy points are
  therefore a slight overestimate for INT-prone QBs.
- **Packaged `workbook_{season}.json` snapshot** is intentionally slim
  synthetic data (Task 6), but it must include at least one `games` entry that
  lines up with its team/week rates so the stale-snapshot path can still
  return `stale: true` with a usable board shape.
