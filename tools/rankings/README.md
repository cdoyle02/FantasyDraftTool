# Expert rankings generator

Builds the committed PPR draft board for the DVS engine. The app never fetches
projections at runtime. Re-run this script, commit the outputs, and rebuild
when you want a new board.

## Data sources

| Positions | Source |
|-----------|--------|
| QB, RB, WR, TE | Fantasy Footballers workbook (`data/footballers-2026.xlsx`) — equal-weight average of Mike, Andy, and Jason counting stats, converted to season-total full PPR |
| K, DST | FantasyPros expert pool when `FANTASYPROS_API_KEY` is set; otherwise bundled rows in `board.py` |

Skill-position ranks are derived **within each position** from averaged PPR
points (no rank-residual nudge). K/DST still use the specialist rank residual.

## Outputs

- `apps/web/src/data/expertRankings.json` — loaded on first visit
- `tools/rankings/out/expert-rankings.csv` — same rows, Import CSV compatible

## How to refresh

```bash
# Default: Footballers workbook + bundled K/DST + ESPN live ADP
uv run python tools/rankings/generate.py

# Same, but skip live FantasyPros (K/DST from board.py)
uv run python tools/rankings/generate.py --from-data

# Optional: refresh K/DST from FantasyPros when a key is set
set FANTASYPROS_API_KEY=your_key
uv run python tools/rankings/generate.py

# Legacy inbox path for tests / manual overrides
uv run python tools/rankings/generate.py --inbox
```

Drop FantasyPros exports into `inbox/` (one rankings file per position, plus
`projections.csv` and `adp.csv`) when using `--inbox`. Optional ESPN/Sleeper
columns or `espn-adp.csv` / `sleeper-adp.csv` attach platform ADPs.

Replace `data/footballers-2026.xlsx` (or set `footballersWorkbook` in
`experts.json`) when the Footballers UDK projections update.

Edit `experts.json` for season, scoring, gap-tier threshold, or K/DST expert
pools. Skill positions list Mike/Andy/Jason for bundle metadata only.

Generate attaches ESPN ADP from [Live Draft Trends](https://fantasy.espn.com/football/livedraftresults)
(`AVG PICK` / `ownership.averageDraftPosition`) and writes a snapshot to
`tools/rankings/data/espn-adp.csv`. A private `ESPN_LEAGUE_ID` still overrides
that public board. Sleeper has no official ADP API, so Sleeper values come from
inbox CSVs or any Sleeper field FantasyPros already returns.

There is no in-app "refresh from the internet" button. User boosts, fades, and
tags live in a separate IndexedDB table and survive **Load bundled rankings**.
