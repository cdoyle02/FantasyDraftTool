"""Parser tests for nflverse SoS CSV normalization (no network)."""

from draft_api.sos.nflverse import (
    completed_game_keys_from_schedule,
    merge_skill_and_dst,
    normalize_team,
    parse_schedule_csv,
    parse_stats_csv,
    parse_team_dst_csv,
    schedule_points_allowed,
)

STATS_CSV = """season,week,season_type,position,team,opponent_team,fantasy_points_ppr
2026,1,REG,RB,LA,WSH,12.5
2026,1,REG,RB,LA,WSH,7.5
2026,1,REG,WR,LA,WSH,20.0
2026,1,REG,RB,WSH,LA,10.0
2026,1,POST,RB,LA,WSH,99.0
2025,1,REG,RB,LA,WSH,50.0
"""

TEAM_CSV = """season,week,season_type,team,opponent_team,def_sacks,def_interceptions,fumble_recovery_opp,def_tds,special_teams_tds,def_safeties,def_punt_blocks,def_fg_blocks,def_pat_blocks,pt_return_tds
2026,1,REG,LA,WSH,2,1,0,0,0,0,0,0,0,0
2026,1,REG,WSH,LA,1,0,1,1,0,0,1,0,0,0
"""

SCHEDULE_CSV = """season,game_type,week,away_team,away_score,home_team,home_score
2026,REG,1,LA,14,WSH,21
2026,REG,2,LA,,WSH,
2026,REG,3,SF,10,SEA,17
2026,POST,1,LA,7,WSH,3
"""


def test_normalize_team_aliases():
    assert normalize_team("LA") == "LAR"
    assert normalize_team("WSH") == "WAS"
    assert normalize_team("lar") == "LAR"
    assert normalize_team("KC") == "KC"


def test_parse_stats_aggregates_position_points_and_aliases():
    skill = parse_stats_csv(STATS_CSV, season=2026)
    assert len(skill) == 2
    lar = skill[(1, "LAR", "WAS")]
    assert lar["RB"] == 20.0  # 12.5 + 7.5
    assert lar["WR"] == 20.0
    assert lar["QB"] == 0.0
    assert lar["DST"] == 0.0
    was = skill[(1, "WAS", "LAR")]
    assert was["RB"] == 10.0


def test_parse_schedule_marks_byes_and_aliases():
    schedule = parse_schedule_csv(SCHEDULE_CSV, season=2026)
    assert schedule["LAR"][1] == "WAS"
    assert schedule["WAS"][1] == "LAR"
    assert schedule["LAR"][2] == "WAS"
    # Week 3 not on LAR schedule → bye
    assert schedule["LAR"][3] is None
    assert schedule["SF"][3] == "SEA"


def test_completed_game_keys_require_scores():
    keys = completed_game_keys_from_schedule(SCHEDULE_CSV, season=2026)
    assert (1, "LAR", "WAS") in keys
    assert (1, "WAS", "LAR") in keys
    assert (2, "LAR", "WAS") not in keys
    assert (3, "SF", "SEA") in keys


def test_dst_points_from_team_stats_and_points_allowed():
    allowed = schedule_points_allowed(SCHEDULE_CSV, season=2026)
    # LAR allowed 21 (WAS score); WAS allowed 14 (LAR score)
    assert allowed[(1, "LAR")] == 21.0
    assert allowed[(1, "WAS")] == 14.0
    dst = parse_team_dst_csv(TEAM_CSV, season=2026, points_allowed_by_team=allowed)
    # LAR D/ST vs WAS: 2 sacks + 1 INT + PA 21 → 2+2+0 = 4
    assert dst[(1, "LAR", "WAS")] == 4.0
    # WAS D/ST vs LAR: 1 sack + 1 FR + 1 def TD + 1 block + PA 14 → 1+2+6+2+1 = 12
    assert dst[(1, "WAS", "LAR")] == 12.0


def test_merge_skill_and_dst_keeps_both():
    skill = parse_stats_csv(STATS_CSV, season=2026)
    allowed = schedule_points_allowed(SCHEDULE_CSV, season=2026)
    dst = parse_team_dst_csv(TEAM_CSV, season=2026, points_allowed_by_team=allowed)
    games = merge_skill_and_dst(skill, dst)
    lar = next(g for g in games if g.offense == "LAR" and g.defense == "WAS")
    assert lar.points["RB"] == 20.0
    assert lar.points["DST"] == 4.0
