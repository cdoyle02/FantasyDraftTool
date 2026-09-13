# Kyle Weekly DST Rankings + League Cross-Ref

**Date:** 2026-09-13  
**Status:** Approved

## Goal

Show Kyle Krajewski’s current-week FantasyPros DST rankings on the Week D/ST page, map them to ESPN FREEAGENT/WAIVERS defenses for a selected league, and ship a Claude skill that prints the full board plus that cross-ref.

## Decisions

| Topic | Choice |
|-------|--------|
| League list | Committed `espn_leagues.json` (`id` + `name`) |
| Kyle data | Scrape public FantasyPros expert page (not official API) |
| Skill | Full rankings **and** ESPN cross-ref |
| UI | New section **below** existing Vegas odds board |
| Auth | `ESPN_S2` / `ESPN_SWID` from env only; never log/return |

## Architecture

Approach A: `apps/api` owns scrape + ESPN + league list for the UI. Claude skill `kyle-weekly-dst` is a stdlib twin (same pattern as `ted-blueprint-weekly-def` / `jared-smola-weekly-k`).

### API

- `GET /api/v1/espn/leagues` → `{ leagues: [{ id, name }] }`
- `GET /api/v1/nfl/kyle-dst-rankings` → week, source URL, full rankings
- `GET /api/v1/nfl/kyle-dst-available?leagueId=` → rankings + available FA/WAIVERS in Kyle order

Scrape TTL ~30–60 minutes (process-local).

### UI

Preserve odds board. Below it: league dropdown (`localStorage`), full Kyle table, available-in-league table. Odds and Kyle errors are isolated.

### Skill

Always print full Kyle DST markdown table; print cross-ref when a league resolves. Explicit-run only.

## Errors

- Scrape fail → 503 `kyle_rankings_unavailable`
- ESPN fail → 503 `espn_unavailable` on availability endpoint only
- Unknown league → 404

## Testing

HTML fixture parser tests, ESPN join tests, API endpoint tests, WeekDstView tests, skill script against fixture.
