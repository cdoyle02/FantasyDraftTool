# ESPN roster snapshots

Current-season rosters for the ESPN leagues in
[`espn_leagues.json`](../../apps/api/src/draft_api/data/espn_leagues.json).

Generate or refresh from `tools/espn-mcp` (needs `ESPN_S2` and `ESPN_SWID`):

```bash
uv run python scripts/export_my_rosters.py
```

| File | Contents |
| --- | --- |
| `current-teams.json` | Nested snapshot: season, scoring period, owners, teams, players |
| `current-teams.csv` | One row per rostered player |

Full behavior, owner matching, and column list:
[`tools/espn-mcp/README.md`](../../tools/espn-mcp/README.md#roster-snapshot).
