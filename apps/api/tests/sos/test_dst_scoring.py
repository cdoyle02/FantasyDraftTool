from draft_api.sos.dst_scoring import dst_fantasy_points, points_allowed_fantasy


def test_points_allowed_brackets():
    assert points_allowed_fantasy(0) == 10.0
    assert points_allowed_fantasy(6) == 7.0
    assert points_allowed_fantasy(13) == 4.0
    assert points_allowed_fantasy(17) == 1.0
    assert points_allowed_fantasy(21) == 0.0
    assert points_allowed_fantasy(27) == -1.0
    assert points_allowed_fantasy(34) == -4.0
    assert points_allowed_fantasy(35) == -5.0


def test_dst_fantasy_points_sums_components():
    # 3 sacks + 1 INT + 1 FR + 0 TD + 1 block + PA 10 (→4 bracket)
    total = dst_fantasy_points(
        sacks=3,
        interceptions=1,
        fumble_recoveries=1,
        defensive_tds=0,
        special_teams_tds=0,
        safeties=0,
        blocked_kicks=1,
        points_allowed=10,
    )
    assert total == 3 + 2 + 2 + 2 + 4
