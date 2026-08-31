# Expert rankings generator

Builds the committed PPR draft board from a pool of high-accuracy FantasyPros
draft experts. The app never talks to FantasyPros. Re-run this script, commit
the outputs, and rebuild when you want a new board.

## Outputs

- `apps/web/src/data/expertRankings.json` — loaded on first visit
- `tools/rankings/out/expert-rankings.csv` — same rows, Import CSV compatible

## How to refresh

```bash
# Preferred: official API (key stays in the environment, never in the app)
set FANTASYPROS_API_KEY=your_key
uv run python tools/rankings/generate.py

# Or drop FantasyPros exports into inbox/ (one rankings file per position,
# plus projections.csv and adp.csv)
uv run python tools/rankings/generate.py --inbox

# Offline bootstrap used when neither a key nor inbox CSVs are present
uv run python tools/rankings/generate.py --from-data
```

Edit `experts.json` to change the per-position pool, season, scoring, or the
rank-residual constant `k`. A six-spot specialist bump is a few points, not a
new WR1.

There is no in-app "refresh from the internet" button. User boosts, fades, and
tags live in a separate IndexedDB table and survive **Load bundled rankings**.
