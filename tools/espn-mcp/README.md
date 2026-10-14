# ESPN fantasy MCP

An MCP server for ESPN's undocumented fantasy football v3 API. The stdio
command is for local Cursor use. `espn-mcp-http` is the hosted Streamable HTTP
connector for Claude. It is not a dependency of the web app.

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
| `espn_status` | Reports the resolved season, league, profile, and credential state, and confirms ESPN is reachable. |
| `espn_league_rosters` | Live rosters for every team in a configured league, or one owner. Katie's hosted login defaults to her team. |
| `espn_league_directory` | Configured league names and ids. |
| `espn_transactions` | Waiver / add-drop / roster / trade history (`mTransactions2`) with player names, pending claims, waiver ranks, and team counters. |
| `kyle_dst_available` | Kyle Krajewski weekly DST ranks crossed with free-agent defenses in one league. |
| `jared_k_available` | Jared Smola weekly kicker ranks crossed with free-agent kickers in one league. |
| `week_odds` | Current-week NFL spreads, totals, and ranked favorite D/ST plays. |
| `ballers_latest` | Newest Fantasy Footballers episode summary, plus YouTube captions when published. |

## Configuration

Copy `.env.example` to `.env` in this directory and fill in what applies:

| Variable | Notes |
| --- | --- |
| `ESPN_SEASON` | Defaults to 2026. |
| `ESPN_LEAGUE_ID` | Optional default. The `leagueId` query parameter in a fantasy.espn.com URL. Tools also accept `league_id` per call. |
| `ESPN_S2`, `ESPN_SWID` | Private leagues only. Copy from DevTools -> Application -> Cookies -> `https://fantasy.espn.com` in a logged-in browser. Keep the curly braces on `SWID`. |
| `ESPN_S2_KATIE`, `ESPN_SWID_KATIE` | Katie's ESPN cookies for her hosted login. |
| `MCP_AUTH_TOKEN`, `MCP_AUTH_TOKEN_KATIE` | Bearer tokens for the hosted `/mcp` endpoint. |
| `MCP_LOGIN_PASSWORD` | Password typed on the ChatGPT sign-in page for Michael. |
| `MCP_PUBLIC_URL` | Public origin of the hosted server, with no trailing slash. |

Credentials are read from the environment only. They are never tool arguments,
so cookie values cannot reach a model transcript, and they are redacted from
error messages. `.env` is gitignored.

Public leagues work with no credentials at all, as do the league-independent
player and season endpoints.

## Roster snapshot

`scripts/export_my_rosters.py` writes a compact JSON and CSV of the current
rosters for the teams you own in the leagues listed in
[`apps/api/src/draft_api/data/espn_leagues.json`](../../apps/api/src/draft_api/data/espn_leagues.json).
It is a local snapshot, not an MCP tool and not a runtime dependency of the app.

Private-league cookies are required (`ESPN_S2` and `ESPN_SWID` in this
directory's `.env`). The script never prints cookie values. It includes:

- every team owned by the ESPN account in `.env`
- plus **Michael Doyle** (`Doyle.m`) and **Katie Doyle** when those members are
  in a reachable league (household export)
- with `--full-leagues` (default): every team in each reachable league under
  `data/rosters/leagues/`

From this directory:

```bash
uv run python scripts/export_my_rosters.py --full-leagues
```

Optional `--out-dir` overrides the default output folder. Files written:

| File | Contents |
| --- | --- |
| [`data/rosters/current-teams.json`](../../data/rosters/current-teams.json) | Household teams (Michael + Katie) |
| [`data/rosters/current-teams.csv`](../../data/rosters/current-teams.csv) | One row per rostered player on those teams |
| `data/rosters/leagues/<id>-<name>.json` | Full league dumps for leagues the cookie can access |

Leagues the session cannot open (e.g. Just The Tip on a Girls Who Ball cookie)
are skipped with a printed note. Re-run to refresh; files are overwritten in place.

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

## Hosted connector

`espn-mcp-http` serves the same tools over stateless Streamable HTTP at `/mcp`.
`/health` is public. Claude sends `Authorization: Bearer <token>`. ChatGPT
signs in through the OAuth page and then sends the access token it received.

| Token | ESPN cookies | Default roster |
| --- | --- | --- |
| `MCP_AUTH_TOKEN` | `ESPN_S2`, `ESPN_SWID` | Names only until a league or owner is requested |
| `MCP_AUTH_TOKEN_KATIE` | `ESPN_S2_KATIE`, `ESPN_SWID_KATIE` | The team her SWID owns |

Build from the repository root:

```bash
docker build -f tools/espn-mcp/Dockerfile .
```

In Claude, add a custom connector with the public `/mcp` URL, choose no sign-in,
and set the request header `Authorization` to `Bearer <that person's token>`.

In ChatGPT, add the same `/mcp` URL as an app with OAuth. The sign-in page asks
who is connecting and checks `MCP_LOGIN_PASSWORD`. Set `MCP_PUBLIC_URL` to the
public origin so the OAuth issuer matches the host ChatGPT calls.

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
