"""Pure FPA / PAE calculator fixtures."""

from draft_api.sos.calculate import (
    CompletedGame,
    build_sos_payload,
    defensive_fpa,
    defensive_pae,
    rank_defenses,
)

# Four-team mini-league, two completed weeks.
# Week 1: AAA vs BBB, CCC vs DDD
# Week 2: AAA vs CCC, BBB vs DDD
# Week 3: AAA bye, BBB vs CCC (scheduled, not played), DDD bye
#
# RB points (offense → points that game):
#   W1 AAA@BBB: AAA scores 20, BBB scores 10  → BBB defense allowed 20, AAA allowed 10
#   W1 CCC@DDD: CCC scores 30, DDD scores 0   → DDD allowed 30 (shutout offense), CCC allowed 0
#   W2 AAA@CCC: AAA scores 14, CCC scores 16  → CCC allowed 14, AAA allowed 16
#   W2 BBB@DDD: BBB scores 12, DDD scores 8   → DDD allowed 12, BBB allowed 8

TEAMS = ["AAA", "BBB", "CCC", "DDD"]


def _pts(rb: float) -> dict:
    return {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0}


GAMES = [
    CompletedGame(week=1, offense="AAA", defense="BBB", points=_pts(20)),
    CompletedGame(week=1, offense="BBB", defense="AAA", points=_pts(10)),
    CompletedGame(week=1, offense="CCC", defense="DDD", points=_pts(30)),
    CompletedGame(week=1, offense="DDD", defense="CCC", points=_pts(0)),
    CompletedGame(week=2, offense="AAA", defense="CCC", points=_pts(14)),
    CompletedGame(week=2, offense="CCC", defense="AAA", points=_pts(16)),
    CompletedGame(week=2, offense="BBB", defense="DDD", points=_pts(12)),
    CompletedGame(week=2, offense="DDD", defense="BBB", points=_pts(8)),
]

SCHEDULE = {
    "AAA": {1: "BBB", 2: "CCC", 3: None, 4: "DDD"},
    "BBB": {1: "AAA", 2: "DDD", 3: "CCC", 4: "CCC"},
    "CCC": {1: "DDD", 2: "AAA", 3: "BBB", 4: "BBB"},
    "DDD": {1: "CCC", 2: "BBB", 3: None, 4: "AAA"},
}
# Pad weeks 5–18 as byes for schedule completeness in cells.
for team in TEAMS:
    for week in range(5, 19):
        SCHEDULE[team][week] = None


def test_fpa_means_and_shutout_as_zero():
    fpa = defensive_fpa(GAMES, "RB")
    # AAA: allowed 10 (W1) + 16 (W2) → 13
    assert fpa["AAA"] == 13.0
    # BBB: allowed 20 (W1) + 8 (W2) → 14
    assert fpa["BBB"] == 14.0
    # CCC: allowed 0 (W1 shutout) + 14 (W2) → 7
    assert fpa["CCC"] == 7.0
    # DDD: allowed 30 (W1) + 12 (W2) → 21
    assert fpa["DDD"] == 21.0


def test_pae_leave_one_out():
    pae = defensive_pae(GAMES, "RB")
    # AAA offense averages: W1=20, W2=14 → leave-one-out for W1 vs BBB expected=14,
    # residual for BBB = 20-14 = 6. For W2 vs CCC expected=20, residual CCC = 14-20 = -6.
    # BBB offense: W1=10, W2=12 → W1 vs AAA residual AAA = 10-12 = -2;
    #               W2 vs DDD residual DDD = 12-10 = 2.
    # CCC offense: W1=30, W2=16 → W1 vs DDD residual DDD = 30-16 = 14;
    #               W2 vs AAA residual AAA = 16-30 = -14.
    # DDD offense: W1=0, W2=8 → W1 vs CCC residual CCC = 0-8 = -8;
    #              W2 vs BBB residual BBB = 8-0 = 8.
    #
    # Defense AAA residuals: -2, -14 → mean -8
    # Defense BBB residuals: 6, 8 → mean 7
    # Defense CCC residuals: -6, -8 → mean -7
    # Defense DDD residuals: 14, 2 → mean 8
    assert pae["AAA"] == -8.0
    assert pae["BBB"] == 7.0
    assert pae["CCC"] == -7.0
    assert pae["DDD"] == 8.0


def test_rank_defenses_highest_is_easiest():
    ranks = rank_defenses({"DDD": 21.0, "BBB": 14.0, "AAA": 13.0, "CCC": 7.0}, TEAMS)
    assert ranks["DDD"] == 1
    assert ranks["BBB"] == 2
    assert ranks["AAA"] == 3
    assert ranks["CCC"] == 4


def test_sos_window_excludes_bye_and_ranks_easiest_first():
    # Window weeks 1–3: AAA has BBB, CCC, bye → avg of BBB FPA(14) + CCC FPA(7) = 10.5
    # BBB has AAA(13), DDD(21), CCC(7) → 13.666…
    # CCC has DDD(21), AAA(13), BBB(14) → 16
    # DDD has CCC(7), BBB(14), bye → 10.5
    # Tie AAA/DDD on 10.5 → AAA sorts before DDD alphabetically but BOTH are hardest
    # (lowest avg). Easiest first = highest avg: CCC, BBB, then AAA, DDD.
    payload = build_sos_payload(
        season=2026,
        position="RB",
        metric="fpa",
        start_week=1,
        end_week=3,
        games=GAMES,
        season_schedule=SCHEDULE,
        teams=TEAMS,
    )
    assert [row.team for row in payload.teams] == ["CCC", "BBB", "AAA", "DDD"]
    assert [row.rank for row in payload.teams] == [1, 2, 3, 4]
    assert payload.teams[0].opponent_average == 16.0
    assert payload.rated_through_week == 2

    aaa = next(row for row in payload.teams if row.team == "AAA")
    week3 = aaa.weeks[2]
    assert week3.week == 3
    assert week3.bye is True
    assert week3.opponent is None
    assert week3.in_window is True
    # Bye excluded from average: only weeks 1–2
    assert aaa.opponent_average == 10.5


def test_week_cells_use_opponent_defense_rank():
    payload = build_sos_payload(
        season=2026,
        position="RB",
        metric="fpa",
        start_week=1,
        end_week=2,
        games=GAMES,
        season_schedule=SCHEDULE,
        teams=TEAMS,
    )
    aaa = next(row for row in payload.teams if row.team == "AAA")
    # Week 1 opponent BBB has FPA 14 → rank 2
    assert aaa.weeks[0].opponent == "BBB"
    assert aaa.weeks[0].opponent_rank == 2
    assert aaa.weeks[0].opponent_value == 14.0
    # Week 2 opponent CCC has FPA 7 → rank 4
    assert aaa.weeks[1].opponent == "CCC"
    assert aaa.weeks[1].opponent_rank == 4


def test_outside_window_cells_marked_but_still_present():
    payload = build_sos_payload(
        season=2026,
        position="RB",
        metric="fpa",
        start_week=2,
        end_week=2,
        games=GAMES,
        season_schedule=SCHEDULE,
        teams=TEAMS,
    )
    aaa = next(row for row in payload.teams if row.team == "AAA")
    assert aaa.weeks[0].in_window is False
    assert aaa.weeks[1].in_window is True
    assert len(aaa.weeks) == 18
