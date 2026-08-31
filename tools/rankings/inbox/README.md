Drop exported FantasyPros CSVs here when you do not have `FANTASYPROS_API_KEY`.

Required:

- `projections.csv` — Player, Team, POS, FPTS
- `rankings-QB.csv` … `rankings-DST.csv` — Rank, Player, Team, POS, Tier

Optional:

- `adp.csv` — Player, Team, POS, ADP (market ADP; missing values default to 250)
- `consensus-QB.csv` … `consensus-DST.csv` — unfiltered ECR, used for the FPTS nudge

Then run `uv run python tools/rankings/generate.py --inbox`.
