"""Tier 2 EPA-allowed defensive rates."""

from draft_api.sos.tier2_epa import (
    EpaGameTotal,
    build_defense_epa_softness_index,
    defensive_epa_allowed_per_game,
    shrunk_defensive_epa,
)
from draft_api.sos.tier1 import DefenseSoftness


def _qb_stat(*, week: int, team: str, opp: str, epa: str) -> dict[str, str]:
    return {
        "season": "2026",
        "week": str(week),
        "season_type": "REG",
        "position": "QB",
        "team": team,
        "opponent_team": opp,
        "passing_epa": epa,
    }


def _receiver_stat(
    *,
    week: int,
    team: str,
    opp: str,
    position: str,
    epa: str,
) -> dict[str, str]:
    return {
        "season": "2026",
        "week": str(week),
        "season_type": "REG",
        "position": position,
        "team": team,
        "opponent_team": opp,
        "receiving_epa": epa,
    }


def test_wr_epa_allowed_sums_receiving_per_game():
    rows = [
        _receiver_stat(week=1, team="AAA", opp="BBB", position="WR", epa="4"),
        _receiver_stat(week=1, team="AAA", opp="BBB", position="WR", epa="2"),
        _receiver_stat(week=1, team="AAA", opp="BBB", position="TE", epa="99"),
    ]
    games = defensive_epa_allowed_per_game(rows, position="WR")
    assert len(games) == 1
    assert games[0].defense == "BBB"
    assert games[0].total_epa == 6.0


def test_te_epa_allowed_uses_receiving_epa():
    rows = [
        _receiver_stat(week=1, team="AAA", opp="BBB", position="TE", epa="3.5"),
        _receiver_stat(week=1, team="AAA", opp="BBB", position="WR", epa="1"),
    ]
    games = defensive_epa_allowed_per_game(rows, position="TE")
    assert len(games) == 1
    assert games[0].total_epa == 3.5


def test_qb_epa_allowed_sums_per_game():
    rows = [
        _qb_stat(week=1, team="AAA", opp="BBB", epa="5"),
        _qb_stat(week=1, team="AAA", opp="BBB", epa="3"),
        _qb_stat(week=1, team="CCC", opp="DDD", epa="1"),
    ]
    games = defensive_epa_allowed_per_game(rows, position="QB")
    assert len(games) == 2
    bbb_game = next(g for g in games if g.defense == "BBB")
    assert bbb_game.total_epa == 8.0


def test_shrunk_epa_n_zero_uses_prior():
    games = [
        EpaGameTotal(week=1, offense="AAA", defense="BBB", total_epa=10.0),
        EpaGameTotal(week=1, offense="CCC", defense="DDD", total_epa=2.0),
    ]
    shrunk = shrunk_defensive_epa(games, position="QB", teams=["BBB", "DDD", "ZZZ"])
    assert shrunk["ZZZ"] is not None
    prior = (10.0 + 2.0) / 2
    assert shrunk["ZZZ"] == prior  # n=0 → prior


def test_epa_softness_rank_high_allowed_is_soft():
    rows = [
        _qb_stat(week=1, team="AAA", opp="SOFT", epa="20"),
        _qb_stat(week=1, team="BBB", opp="TOUGH", epa="2"),
        _qb_stat(week=2, team="AAA", opp="SOFT", epa="18"),
        _qb_stat(week=2, team="BBB", opp="TOUGH", epa="1"),
    ]
    from draft_api.sos.calculate import CompletedGame

    completed = [
        CompletedGame(week=1, offense="AAA", defense="SOFT", points={"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DST": 0}),
        CompletedGame(week=1, offense="BBB", defense="TOUGH", points={"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DST": 0}),
        CompletedGame(week=2, offense="AAA", defense="SOFT", points={"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DST": 0}),
        CompletedGame(week=2, offense="BBB", defense="TOUGH", points={"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DST": 0}),
    ]
    _, _, softness = build_defense_epa_softness_index(
        position="QB",
        window="season",
        games=completed,
        stats_rows=rows,
        teams=["SOFT", "TOUGH"],
    )
    assert softness["SOFT"].rank == 1
    assert softness["TOUGH"].rank == 2
    assert softness["SOFT"].softness == "soft"
