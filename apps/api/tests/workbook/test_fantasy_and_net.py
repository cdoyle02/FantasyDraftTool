"""Workbook net matchup helpers and positional fantasy scoring."""

from draft_api.workbook.calculate import comb_net_dsr, mean_net, net_dsr_diff
from draft_api.workbook.fantasy import receiving_points


def test_mean_net_averages():
    assert mean_net(10.0, 20.0) == 15.0
    assert mean_net(None, 20.0) is None


def test_comb_and_diff():
    assert comb_net_dsr(0.6, 0.8) == 0.7
    assert net_dsr_diff(0.7, 0.5) == 0.2


def test_ppr_vs_half():
    assert receiving_points(receptions=5, yards=50, tds=1, scoring="ppr") == 16.0
    assert receiving_points(receptions=5, yards=50, tds=1, scoring="half_ppr") == 13.5
