"""Tier 1 shrunk aFPA, softness buckets, and rolling window helpers."""

from draft_api.sos.calculate import (
    CompletedGame,
    SHRINK_K,
    rank_defenses_shrunk,
    resolve_sos_window,
    shrink_afpa,
    softness_bucket,
)
from draft_api.sos.tier1 import build_tier1_grid


def test_shrink_afpa_n_zero_returns_prior():
    assert shrink_afpa(None, prior=18.5, n=0) == 18.5
    assert shrink_afpa(22.0, prior=18.5, n=0) == 18.5


def test_shrink_afpa_blends_toward_prior():
    # n=4, k=4: equal weight → midpoint
    assert shrink_afpa(22.0, prior=18.0, n=4, k=4) == 20.0


def test_shrink_afpa_large_n_approaches_raw():
    value = shrink_afpa(22.0, prior=18.0, n=10_000, k=SHRINK_K)
    assert value is not None and abs(value - 22.0) < 0.01


def test_softness_bucket_boundaries():
    assert softness_bucket(7) == ("soft", 1.0)
    assert softness_bucket(8) == ("neutral", 0.5)
    assert softness_bucket(25) == ("neutral", 0.5)
    assert softness_bucket(26) == ("tough", 0.0)
    assert softness_bucket(27) == ("tough", 0.0)
    assert softness_bucket(1) == ("soft", 1.0)


def test_rank_defenses_shrunk_highest_is_softest():
    ranks = rank_defenses_shrunk(
        {
            "AAA": 25.0,
            "BBB": 20.0,
            "CCC": None,
        },
        teams=["AAA", "BBB", "CCC", "DDD"],
    )
    assert ranks["AAA"] == 1
    assert ranks["BBB"] == 2
    assert ranks["CCC"] == 3
    assert ranks["DDD"] == 4


def test_resolve_sos_window_l8_size():
    weeks = resolve_sos_window("l8", rated_through_week=10)
    assert weeks == {3, 4, 5, 6, 7, 8, 9, 10}
    assert len(weeks) == 8


def test_resolve_sos_window_l4():
    weeks = resolve_sos_window("l4", rated_through_week=10)
    assert weeks == {7, 8, 9, 10}


def test_resolve_sos_window_season_to_date():
    weeks = resolve_sos_window("season", rated_through_week=6)
    assert weeks == {1, 2, 3, 4, 5, 6}


def test_resolve_sos_window_empty_when_no_games():
    assert resolve_sos_window("l8", rated_through_week=0) == set()


def _mini_games() -> list[CompletedGame]:
    pts = lambda rb: {"QB": 0.0, "RB": rb, "WR": 0.0, "TE": 0.0, "DST": 0.0}
    return [
        CompletedGame(week=1, offense="AAA", defense="BBB", points=pts(20)),
        CompletedGame(week=1, offense="BBB", defense="AAA", points=pts(10)),
        CompletedGame(week=2, offense="AAA", defense="CCC", points=pts(14)),
        CompletedGame(week=2, offense="CCC", defense="AAA", points=pts(16)),
    ]


def test_build_tier1_grid_week_cells_include_shrunk_afpa_and_softness():
    schedule = {
        "AAA": {w: None for w in range(1, 19)},
        "BBB": {w: None for w in range(1, 19)},
        "CCC": {w: None for w in range(1, 19)},
    }
    schedule["AAA"][1] = "BBB"
    schedule["AAA"][2] = "CCC"
    schedule["BBB"][1] = "AAA"
    schedule["CCC"][2] = "AAA"
    payload = build_tier1_grid(
        season=2026,
        position="RB",
        window="season",
        start_week=1,
        end_week=2,
        games=_mini_games(),
        season_schedule=schedule,
        teams=["AAA", "BBB", "CCC"],
    )
    aaa = next(row for row in payload.teams if row.team == "AAA")
    w1 = next(cell for cell in aaa.weeks if cell.week == 1)
    assert w1.opponent == "BBB"
    assert w1.shrunk_afpa is not None
    assert w1.rank is not None
    assert w1.softness in ("soft", "neutral", "tough")
    assert w1.softness_score in (0.0, 0.5, 1.0)
