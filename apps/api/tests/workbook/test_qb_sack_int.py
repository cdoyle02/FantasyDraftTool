"""QB Sack% + INT enrichment from weekly stats / PBP."""

from __future__ import annotations

from draft_api.workbook.nflverse import (
    PositionalWeekRate,
    enrich_qb_rates_from_pbp,
    parse_positional_stats,
)
from draft_api.workbook.service import _rate_metrics


STATS_WITH_INT_SACK = """season,week,season_type,player_id,player_display_name,position,team,opponent_team,targets,receptions,receiving_yards,receiving_tds,carries,rushing_yards,rushing_tds,passing_yards,passing_tds,attempts,interceptions,sacks,fantasy_points_ppr
2026,5,REG,00-1,Starter,QB,AAA,BBB,0,0,0,0,2,10,0,250,2,30,1,3,20.0
"""

PBP_SACK_INT = """season,season_type,week,game_id,play_id,posteam,defteam,drive,qb_kneel,pass_attempt,rush_attempt,yards_gained,epa,xpass,series_success,touchdown,complete_pass,receiver_player_id,sack,interception
2026,REG,5,g1,1,AAA,BBB,1,0,1,0,10,0.1,0.5,1,0,1,,0,0
2026,REG,5,g1,2,AAA,BBB,1,0,1,0,-8,-1.0,0.6,0,0,0,,1,0
2026,REG,5,g1,3,AAA,BBB,1,0,1,0,0,-2.0,0.5,0,0,0,,0,1
2026,REG,5,g1,4,BBB,AAA,2,0,1,0,5,0.2,0.5,1,0,1,,0,0
"""


def test_parse_positional_stats_reads_optional_int_sack_attempt_columns() -> None:
    off, _def, _pos = parse_positional_stats(STATS_WITH_INT_SACK, season=2026)
    qb = off["qb"][("AAA", 5)]
    assert qb.pass_attempts == 30.0
    assert qb.pass_ints == 1.0
    assert qb.sacks_taken == 3.0


def test_enrich_qb_rates_from_pbp_counts_sacks_and_ints() -> None:
    base = {
        "qb": {
            ("AAA", 5): PositionalWeekRate(pass_yards=250.0, pass_tds=2.0),
            ("BBB", 5): PositionalWeekRate(pass_yards=100.0, pass_tds=0.0),
        }
    }
    off, defense = enrich_qb_rates_from_pbp(PBP_SACK_INT, season=2026, positional_off=base, positional_def={"qb": {}})
    aaa = off["qb"][("AAA", 5)]
    assert aaa.pass_attempts == 3.0  # three AAA pass_attempt rows
    assert aaa.sacks_taken == 1.0
    assert aaa.pass_ints == 1.0
    # BBB defense allowed AAA's sack/int on those plays
    bbb_def = defense["qb"][("BBB", 5)]
    assert bbb_def.sacks_taken == 1.0
    assert bbb_def.pass_ints == 1.0


def test_qb_rate_metrics_include_sack_pct_and_int_penalty() -> None:
    summed = PositionalWeekRate(
        pass_yards=250.0,
        pass_tds=2.0,
        rush_yards=10.0,
        rush_tds=0.0,
        pass_attempts=30.0,
        pass_ints=1.0,
        sacks_taken=3.0,
    )
    metrics = _rate_metrics(summed, 1, group="qb", scoring="ppr", total_targets=0.0)
    # sack% = 3 / (30+3)
    assert metrics["sackPct"] == 3.0 / 33.0
    assert metrics["intG"] == 1.0
    # pass pts: 0.04*250 + 4*2 - 2*1 = 10+8-2 = 16; run 1.0
    assert metrics["fpGPass"] == 16.0
    assert metrics["fpGTot"] == 17.0
