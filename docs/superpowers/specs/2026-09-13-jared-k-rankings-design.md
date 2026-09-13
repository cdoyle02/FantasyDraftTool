# Jared Weekly K Rankings + League Cross-Ref

**Date:** 2026-09-13  
**Status:** Approved

## Goal

Show Jared Smola’s current-week FantasyPros K rankings on a dedicated **Week K** tab, map them to ESPN FREEAGENT/WAIVERS kickers for a selected league, and keep the personal `/jared-smola-weekly-k` skill printing the full board plus that cross-ref.

## Decisions

| Topic | Choice |
|-------|--------|
| UI placement | New shell tab **Week K** (not on Week D/ST) |
| League list | Reuse committed `espn_leagues.json` (`id` + `name`) |
| Jared data | Scrape public FantasyPros expert page (not official API) |
| Skill | Full rankings **and** ESPN cross-ref when league resolves |
| Auth | `ESPN_S2` / `ESPN_SWID` from env only; never log/return |
| Match | Player name (normalized); single-team fallback |
| ESPN slot | **17** (K) |

## Architecture

Same pattern as Kyle DST: `apps/api` owns scrape + ESPN + league list for the UI. Claude/Cursor skill `jared-smola-weekly-k` is a stdlib twin.

### API

- `GET /api/v1/espn/leagues` → shared with Week D/ST
- `GET /api/v1/nfl/jared-k-rankings` → week, source URL, full rankings
- `GET /api/v1/nfl/jared-k-available?leagueId=` → rankings + available FA/WAIVERS in Jared order

Scrape TTL ~30 minutes (`JARED_K_CACHE_TTL_SECONDS`, default 1800).

### UI

`WeekKView`: league dropdown (`localStorage` key `fdt.week-k.leagueId`), full Jared table, available-in-league table. Rankings and ESPN errors are isolated.

### Skill

Always print full Jared K markdown table; print cross-ref when a league resolves. Explicit-run only.

## Errors

- Scrape fail → 503 `jared_rankings_unavailable`
- ESPN fail → 503 `espn_unavailable` on availability endpoint only
- Unknown league → 404

## Testing

HTML fixture parser tests, ESPN name-join tests, API endpoint tests, `WeekKView` tests, skill script against live/fixture paths.
