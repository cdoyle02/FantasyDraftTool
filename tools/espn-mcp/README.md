# ESPN fantasy MCP

A development-time MCP server for exploring ESPN's undocumented fantasy football
v3 API while building ESPN integrations. It is a research tool, not a runtime
dependency of the application.

ESPN publishes no API documentation and changes endpoints without notice, so the
goal here is to make the current shape of the API discoverable and expose a
small set of normalized read tools.

## Tools

| Tool | Purpose |
| --- | --- |
| `espn_reference` | Endpoint paths, the `view` parameter catalog, id lookup tables and known gotchas. No network access. |
| `espn_request` | Call any endpoint. Returns a structural outline by default because payloads are large; switch to `mode="json"` once the relevant subtree is known. Accepts `fantasy_filter` as a JSON object or string. |
| `espn_draft_picks` | Normalized `mDraftDetail` picks plus the `in_progress` flag. This is the ESPN equivalent of polling Sleeper's draft picks endpoint. |
| `espn_league_settings` | Team count, draft configuration, roster slot counts and scoring format from `mSettings`. |
| `espn_players` | Player pool with ESPN player ids for draft id maps. Preserves outer availability metadata when a league is set. |
| `espn_free_agents` | League free agents and waiver players from `kona_player_info` with server-side filters, percent-owned sort, paging, and bounded name search. |
| `espn_status` | Reports the resolved season, league and credential state, and confirms ESPN is reachable. |

## Configuration

Copy `.env.example` to `.env` in this directory and fill in what applies:

| Variable | Notes |
| --- | --- |
| `ESPN_SEASON` | Defaults to 2026. |
| `ESPN_LEAGUE_ID` | Optional default. The `leagueId` query parameter in a fantasy.espn.com URL. Tools also accept `league_id` per call. |
| `ESPN_S2`, `ESPN_SWID` | Private leagues only. Copy from DevTools -> Application -> Cookies -> `https://fantasy.espn.com` in a logged-in browser. Keep the curly braces on `SWID`. |

Credentials are read from the environment only. They are never tool arguments,
so cookie values cannot reach a model transcript, and they are redacted from
error messages. `.env` is gitignored.

Public leagues work with no credentials at all, as do the league-independent
player and season endpoints.

## Registration

The repository ignores `.cursor/`, so `.cursor/mcp.json` is local to this
machine and uses an absolute path:

```json
{
  "mcpServers": {
    "espn-fantasy": {
      "command": "uv",
      "args": ["--directory", "<repo>/tools/espn-mcp", "run", "espn-mcp"]
    }
  }
}
```

Reload the Cursor window after editing that file or `.env`, since the server
reads its environment at startup.

## Checks

```bash
uv run pytest
uv run python scripts/smoke_test.py
uv run python scripts/public_draft_smoke_test.py
uv run python scripts/public_free_agents_smoke_test.py
uvx ruff check .
```

The smoke test performs a real stdio handshake, lists the tools, and calls the
tools that need no league id.

`public_draft_smoke_test.py` and `public_free_agents_smoke_test.py` exercise
normalization against known completed public 2020 leagues without credentials.

## Caveats

- ESPN reads moved to `lm-api-reads.fantasy.espn.com` in April 2024. The older
  `fantasy.espn.com` host is not used here.
- Draft picks carry `playerId` only, so names require a separate player lookup.
- Unfiltered `kona_player_info` returns about 50 players; use `espn_free_agents`
  or a verified `X-Fantasy-Filter` for availability queries.
- Search scans up to 500 ESPN rows with a fixed 100-row internal page size.
- The full player payload is several megabytes. Prefer shape mode, a position
  filter, or a small limit while exploring.
