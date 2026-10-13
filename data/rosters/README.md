# ESPN roster snapshots

Current-season rosters for the ESPN leagues in
[`espn_leagues.json`](../../apps/api/src/draft_api/data/espn_leagues.json).

Generate or refresh from `tools/espn-mcp` (needs `ESPN_S2` and `ESPN_SWID`):

```bash
cd tools/espn-mcp && uv run python scripts/export_my_rosters.py --full-leagues
```

Also runs as step 2 of the Tuesday Ballers pipeline
(`.cursor/skills/ballers-transcripts/scripts/run_tuesday.sh`).

| File | Contents |
| --- | --- |
| `current-teams.json` | Household teams: Michael Doyle + Katie Doyle when present |
| `current-teams.csv` | One row per rostered player on those teams |
| `leagues/<id>-<name>.json` | Full league dumps (every team) for reachable leagues |

Full behavior, owner matching, and column list:
[`tools/espn-mcp/README.md`](../../tools/espn-mcp/README.md#roster-snapshot).
