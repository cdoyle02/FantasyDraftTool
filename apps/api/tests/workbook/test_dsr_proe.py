"""Workbook DSR, explosive play thresholds, and PROE."""

from draft_api.workbook.calculate import (
    DriveOutcome,
    PassPlay,
    drive_success_rate,
    explosive_pass,
    explosive_run,
    pass_rate_over_expectation,
)


def test_drive_success_rate_two_of_three():
    """Kneels excluded upstream; caller supplies only scored drives."""
    drives = [
        DriveOutcome(team="KC", week=1, success=True),
        DriveOutcome(team="KC", week=1, success=True),
        DriveOutcome(team="KC", week=1, success=False),
    ]
    rate = drive_success_rate(drives, team="KC", weeks={1})
    assert rate is not None
    assert abs(rate - 2 / 3) < 1e-9


def test_drive_success_rate_filters_team_and_week():
    drives = [
        DriveOutcome(team="KC", week=1, success=True),
        DriveOutcome(team="KC", week=2, success=False),
        DriveOutcome(team="BUF", week=1, success=True),
    ]
    assert drive_success_rate(drives, team="KC", weeks={1}) == 1.0
    assert drive_success_rate(drives, team="KC", weeks={1, 2}) == 0.5


def test_explosive_thresholds():
    assert explosive_pass(15.0) is False
    assert explosive_pass(15.1) is True
    assert explosive_run(10.0) is False
    assert explosive_run(10.1) is True


def test_proe_known_xpass():
    plays = [
        PassPlay(team="KC", week=1, is_pass=True, xpass=0.5),
        PassPlay(team="KC", week=1, is_pass=False, xpass=0.6),
        PassPlay(team="KC", week=1, is_pass=True, xpass=None),
    ]
    # (0.5 + -0.6) / 2 * 100 = -5.0; play with None xpass skipped
    proe = pass_rate_over_expectation(plays, team="KC", weeks={1})
    assert proe is not None
    assert abs(proe - (-5.0)) < 1e-9
