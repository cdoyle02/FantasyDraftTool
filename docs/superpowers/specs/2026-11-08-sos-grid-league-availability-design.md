# SoS grid league availability

**Date:** 2026-11-08  
**Depends on:** [API dual ESPN profiles](./2026-11-08-api-espn-dual-profiles-design.md)

## Goal

When a fantasy `leagueId` is selected on the Strength of Schedule chart, each TEAM row shows:

- **primaryPlayer** — top opportunity player on that NFL team for the current position (Clay WR role respected); for DST, the team defense
- **leagueAvailability** — `available` | `on_roster` | `taken` | `unknown`

Week-cell softness glyphs are unchanged.

## Rules

- Availability uses the full ESPN league roster (not FA top-N). Not rostered ⇒ `available`.
- `on_roster` when the player is on the cookie owner’s team (SWID match or explicit owner).
- Grid endpoints accept `leagueId` / `espnProfile` the same way as opportunity.

## Surfaces

- API: Tier1 / Tier2 / classic SoS grid responses
- UI: `WeekSosView` TEAM column name + FA / Mine / Taken badge
