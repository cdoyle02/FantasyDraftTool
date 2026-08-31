Drop exported FantasyPros CSVs here when you do not have `FANTASYPROS_API_KEY`.

Required:

- `projections.csv` — Player, Team, POS, FPTS
- `rankings-QB.csv` … `rankings-DST.csv` — Rank, Player, Team, POS, Tier

Optional:

- `adp.csv` — Player, Team, POS, ADP (FantasyPros / market ADP; missing values default to 250). Optional `ESPN` and `Sleeper` columns attach platform ADPs.
- `espn-adp.csv` / `sleeper-adp.csv` — Player, Team, POS, ADP for one platform. These override the matching column on `adp.csv`. ESPN values should be Live Draft Trends **AVG PICK** from https://fantasy.espn.com/football/livedraftresults
- `consensus-QB.csv` … `consensus-DST.csv` — unfiltered ECR, used for the FPTS nudge

Then run `uv run python tools/rankings/generate.py --inbox`.
