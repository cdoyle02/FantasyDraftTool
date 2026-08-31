"""Bundled 2026 K/DST rows used when FantasyPros is unavailable for those positions.

Rows are (name, team, pos, fpts, adp, consensus_rank, pooled_rank, tier).
Specialist ranks differ from consensus on a handful of names so the residual
nudge is visible; everyone else matches consensus.
"""

from __future__ import annotations

from merge import AdpRow, Projection, RankedPlayer

# name, team, pos, fpts, adp, consensus_rank, pooled_rank, tier
_ROWS: tuple[tuple[str, str, str, float, float, int, int, int], ...] = (
    # K
    ("Brandon Aubrey", "DAL", "K", 168.4, 118.2, 1, 1, 1),
    ("Cameron Dicker", "LAC", "K", 161.2, 132.6, 2, 2, 1),
    ("Jake Bates", "DET", "K", 156.8, 141.4, 3, 3, 1),
    ("Ka'imi Fairbairn", "HOU", "K", 152.4, 150.2, 4, 5, 2),
    ("Chase McLaughlin", "TB", "K", 148.0, 159.0, 5, 4, 2),
    ("Harrison Butker", "KC", "K", 143.6, 167.8, 6, 8, 2),
    ("Tyler Loop", "BAL", "K", 139.2, 176.6, 7, 6, 2),
    ("Jason Myers", "SEA", "K", 134.8, 185.4, 8, 7, 3),
    ("Will Reichard", "MIN", "K", 130.4, 194.2, 9, 9, 3),
    ("Chris Boswell", "PIT", "K", 126.0, 203.0, 10, 10, 3),
    ("Younghoe Koo", "ATL", "K", 121.6, 211.8, 11, 11, 3),
    ("Jake Elliott", "PHI", "K", 117.2, 220.6, 12, 12, 4),
    ("Cameron Little", "JAX", "K", 112.8, 229.4, 13, 13, 4),
    ("Matt Gay", "WAS", "K", 108.4, 238.2, 14, 14, 4),
    ("Daniel Carlson", "LV", "K", 104.0, 247.0, 15, 15, 4),
    ("Wil Lutz", "DEN", "K", 99.6, 250.0, 16, 16, 5),
    ("Justin Tucker", "FA", "K", 95.2, 250.0, 17, 20, 5),
    ("Evan McPherson", "CIN", "K", 90.8, 250.0, 18, 17, 5),
    ("Cairo Santos", "CHI", "K", 86.4, 250.0, 19, 19, 5),
    ("Jason Sanders", "MIA", "K", 82.0, 250.0, 20, 18, 5),
    ("Graham Gano", "NYG", "K", 77.6, 250.0, 21, 21, 6),
    ("Chad Ryland", "ARI", "K", 73.2, 250.0, 22, 22, 6),
    ("Nick Folk", "NYJ", "K", 68.8, 250.0, 23, 23, 6),
    ("Brandon McManus", "GB", "K", 64.4, 250.0, 24, 24, 6),
    ("Matt Prater", "BUF", "K", 60.0, 250.0, 25, 25, 7),
    ("Andres Borregales", "NE", "K", 55.6, 250.0, 26, 26, 7),
    ("Joshua Karty", "LAR", "K", 51.2, 250.0, 27, 27, 7),
    ("Jake Moody", "SF", "K", 46.8, 250.0, 28, 28, 7),
    ("Blake Grupe", "NO", "K", 42.4, 250.0, 29, 29, 8),
    ("Eddy Pineiro", "SF", "K", 38.0, 250.0, 30, 30, 8),
    ("Spencer Shrader", "IND", "K", 33.6, 250.0, 31, 31, 8),
    ("Riley Patterson", "CLE", "K", 29.2, 250.0, 32, 32, 8),
    # DST
    ("Eagles DST", "PHI", "DST", 148.6, 122.4, 1, 1, 1),
    ("Ravens DST", "BAL", "DST", 144.2, 136.8, 2, 2, 1),
    ("Broncos DST", "DEN", "DST", 139.8, 147.2, 3, 4, 1),
    ("Steelers DST", "PIT", "DST", 135.4, 158.6, 4, 3, 2),
    ("Vikings DST", "MIN", "DST", 131.0, 169.0, 5, 5, 2),
    ("Texans DST", "HOU", "DST", 126.6, 179.4, 6, 6, 2),
    ("Chiefs DST", "KC", "DST", 122.2, 189.8, 7, 8, 2),
    ("Bills DST", "BUF", "DST", 117.8, 200.2, 8, 7, 3),
    ("Rams DST", "LAR", "DST", 113.4, 210.6, 9, 9, 3),
    ("Seahawks DST", "SEA", "DST", 109.0, 221.0, 10, 10, 3),
    ("49ers DST", "SF", "DST", 104.6, 231.4, 11, 11, 3),
    ("Packers DST", "GB", "DST", 100.2, 241.8, 12, 12, 4),
    ("Chargers DST", "LAC", "DST", 95.8, 250.0, 13, 13, 4),
    ("Lions DST", "DET", "DST", 91.4, 250.0, 14, 14, 4),
    ("Cowboys DST", "DAL", "DST", 87.0, 250.0, 15, 15, 4),
    ("Dolphins DST", "MIA", "DST", 82.6, 250.0, 16, 16, 5),
    ("Bears DST", "CHI", "DST", 78.2, 250.0, 17, 17, 5),
    ("Bengals DST", "CIN", "DST", 73.8, 250.0, 18, 18, 5),
    ("Commanders DST", "WAS", "DST", 69.4, 250.0, 19, 19, 5),
    ("Falcons DST", "ATL", "DST", 65.0, 250.0, 20, 20, 5),
    ("Colts DST", "IND", "DST", 60.6, 250.0, 21, 21, 6),
    ("Buccaneers DST", "TB", "DST", 56.2, 250.0, 22, 22, 6),
    ("Jets DST", "NYJ", "DST", 51.8, 250.0, 23, 23, 6),
    ("Patriots DST", "NE", "DST", 47.4, 250.0, 24, 24, 6),
    ("Cardinals DST", "ARI", "DST", 43.0, 250.0, 25, 25, 7),
    ("Raiders DST", "LV", "DST", 38.6, 250.0, 26, 26, 7),
    ("Saints DST", "NO", "DST", 34.2, 250.0, 27, 27, 7),
    ("Jaguars DST", "JAX", "DST", 29.8, 250.0, 28, 28, 7),
    ("Titans DST", "TEN", "DST", 25.4, 250.0, 29, 29, 8),
    ("Giants DST", "NYG", "DST", 21.0, 250.0, 30, 30, 8),
    ("Panthers DST", "CAR", "DST", 16.6, 250.0, 31, 31, 8),
    ("Browns DST", "CLE", "DST", 12.2, 250.0, 32, 32, 8),
)


def k_dst_board_inputs() -> tuple[
    list[Projection],
    dict[str, list[RankedPlayer]],
    dict[str, list[RankedPlayer]],
    list[AdpRow],
]:
    projections: list[Projection] = []
    pooled: dict[str, list[RankedPlayer]] = {}
    consensus: dict[str, list[RankedPlayer]] = {}
    adp_rows: list[AdpRow] = []
    for name, team, position, fpts, adp, consensus_rank, pooled_rank, tier in _ROWS:
        projections.append(
            Projection(
                name=name,
                team=team,
                position=position,
                fpts=fpts,
                consensus_rank=consensus_rank,
            )
        )
        consensus.setdefault(position, []).append(
            RankedPlayer(name=name, team=team, position=position, rank=consensus_rank, tier=tier)
        )
        pooled.setdefault(position, []).append(
            RankedPlayer(name=name, team=team, position=position, rank=pooled_rank, tier=tier)
        )
        adp_rows.append(AdpRow(name=name, team=team, position=position, adp=adp))
    return projections, pooled, consensus, adp_rows
