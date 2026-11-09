# API dual ESPN profiles

**Date:** 2026-11-08  
**Status:** Implemented on `feature/A.1-nfl-week-dst-odds`

## Problem

The Week API previously read only `ESPN_S2` / `ESPN_SWID`. Girls Who Ball is Katie’s private league; Michael’s cookies return `AUTH_LEAGUE_NOT_VISIBLE`. Operators had to restart the API after swapping env files.

## Design

Mirror hosted MCP’s two cookie pairs without bearer tokens:

| Profile | Env | Default leagues |
|---------|-----|-----------------|
| `michael` | `ESPN_S2`, `ESPN_SWID` | All configured leagues except GWB |
| `katie` | `ESPN_S2_KATIE`, `ESPN_SWID_KATIE` | `1216398267` (Girls Who Ball) |

Resolution: optional query `espnProfile=katie|michael` overrides the league map. Missing cookies for the **resolved** profile fail fast — do **not** try the other profile on ESPN 401.

## Call sites

Kyle/Jared available, Workbook overlay/injuries, SoS opportunity roster join — all pass `leagueId` into `espn_credentials_from_env`.

## Non-goals

Hosted MCP auth changes; browser-held cookies; automatic 401 fallback.
