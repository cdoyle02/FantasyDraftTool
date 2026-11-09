"""Snap-filtered usage shares (Tier 2)."""

from draft_api.sos.tier2_snap import SnapPctIndex, build_snap_pct_index, trim_snap_counts_row
from draft_api.sos.usage import build_usage_index


def _rb_row(*, week: int, team: str, player_id: str, name: str, carries: str) -> dict[str, str]:
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
    }


def test_trim_snap_counts_row_drops_extra_columns():
    row = {
        "season": "2026",
        "week": "1",
        "game_type": "REG",
        "team": "KC",
        "player": "Alpha",
        "offense_pct": "0.55",
        "defense_pct": "0.10",
        "position": "RB",
    }
    trimmed = trim_snap_counts_row(row)
    assert trimmed == {
        "season": "2026",
        "week": "1",
        "game_type": "REG",
        "team": "KC",
        "player": "Alpha",
        "offense_pct": "0.55",
    }


def test_snap_filter_excludes_low_snap_from_denominator():
    stats = [
        _rb_row(week=1, team="KC", player_id="A", name="Starter", carries="18"),
        _rb_row(week=1, team="KC", player_id="B", name="Backup", carries="2"),
    ]
    snap_rows = [
        {"season": "2026", "week": "1", "team": "KC", "player": "Starter", "offense_pct": "0.75"},
        {"season": "2026", "week": "1", "team": "KC", "player": "Backup", "offense_pct": "0.10"},
    ]
    snap_index = build_snap_pct_index(snap_rows, season=2026)
    unfiltered = build_usage_index(stats, position="RB", weeks={1})
    filtered = build_usage_index(
        stats,
        position="RB",
        weeks={1},
        snap_pct_index=snap_index,
        min_offense_snap_pct=0.20,
    )
    assert unfiltered[0].usage_share == 0.9  # 18/20
    assert filtered[0].usage_share == 1.0  # backup excluded from denominator
    assert len(filtered) == 1


def test_missing_snap_row_treated_as_zero_pct_when_index_present():
    stats = [_rb_row(week=1, team="KC", player_id="A", name="Ghost", carries="10")]
    snap_index = SnapPctIndex(by_key={})
    usage = build_usage_index(
        stats,
        position="RB",
        weeks={1},
        snap_pct_index=snap_index,
        min_offense_snap_pct=0.20,
    )
    assert usage == []
