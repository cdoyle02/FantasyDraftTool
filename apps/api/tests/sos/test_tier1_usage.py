"""Tier 1 usage shares from nflverse stats_player_week rows."""

from draft_api.sos.usage import PlayerUsage, build_usage_index


def _rb_row(
    *,
    week: int,
    team: str,
    player_id: str,
    name: str,
    carries: str,
    targets: str = "0",
) -> dict[str, str]:
    return {
        "season": "2026",
        "week": str(week),
        "season_type": "REG",
        "position": "RB",
        "team": team,
        "opponent_team": "BBB",
        "player_id": player_id,
        "player_display_name": name,
        "carries": carries,
        "targets": targets,
    }


def test_rb_usage_share_two_backs_same_team_one_week():
    rows = [
        _rb_row(week=1, team="AAA", player_id="A1", name="Alpha", carries="12"),
        _rb_row(week=1, team="AAA", player_id="A2", name="Beta", carries="8"),
    ]
    usage = build_usage_index(rows, position="RB", weeks={1})
    by_name = {u.player_name: u for u in usage}
    assert by_name["Alpha"].usage_share == 0.6
    assert by_name["Beta"].usage_share == 0.4
    assert by_name["Alpha"].team == "AAA"


def test_usage_excludes_weeks_outside_window():
    rows = [
        _rb_row(week=1, team="AAA", player_id="A1", name="Alpha", carries="10"),
        _rb_row(week=2, team="AAA", player_id="A1", name="Alpha", carries="20"),
    ]
    usage = build_usage_index(rows, position="RB", weeks={2})
    assert len(usage) == 1
    assert usage[0].usage_share == 1.0


def test_wr_targets_share_uses_position_denominator():
    rows = [
        {
            "season": "2026",
            "week": "1",
            "season_type": "REG",
            "position": "WR",
            "team": "KC",
            "opponent_team": "BUF",
            "player_id": "W1",
            "player_display_name": "W One",
            "targets": "6",
            "carries": "0",
        },
        {
            "season": "2026",
            "week": "1",
            "season_type": "REG",
            "position": "WR",
            "team": "KC",
            "opponent_team": "BUF",
            "player_id": "W2",
            "player_display_name": "W Two",
            "targets": "4",
            "carries": "0",
        },
    ]
    usage = build_usage_index(rows, position="WR", weeks={1})
    shares = {u.player_name: u.usage_share for u in usage}
    assert shares["W One"] == 0.6
    assert shares["W Two"] == 0.4


def test_qb_starter_gets_full_share_backup_null():
    rows = [
        {
            "season": "2026",
            "week": "1",
            "season_type": "REG",
            "position": "QB",
            "team": "KC",
            "opponent_team": "BUF",
            "player_id": "Q1",
            "player_display_name": "Starter",
            "passing_yards": "250",
            "carries": "0",
            "targets": "0",
        },
        {
            "season": "2026",
            "week": "1",
            "season_type": "REG",
            "position": "QB",
            "team": "KC",
            "opponent_team": "BUF",
            "player_id": "Q2",
            "player_display_name": "Backup",
            "passing_yards": "0",
            "carries": "0",
            "targets": "0",
        },
    ]
    usage = build_usage_index(rows, position="QB", weeks={1})
    by_name = {u.player_name: u for u in usage}
    assert by_name["Starter"].usage_share == 1.0
    assert by_name["Backup"].usage_share is None


def test_player_usage_dataclass_fields():
    rows = [_rb_row(week=1, team="AAA", player_id="X", name="Solo", carries="5")]
    usage = build_usage_index(rows, position="RB", weeks={1})
    assert len(usage) == 1
    row: PlayerUsage = usage[0]
    assert row.gsis_id == "X"
    assert row.position == "RB"
