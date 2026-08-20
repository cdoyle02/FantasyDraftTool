import pytest

from dvs_engine import CsvImportError, Position, import_players_csv


def test_fantasypros_headers_are_normalized():
    result = import_players_csv(
        "Player,Team,POS,FPTS,ADP,Tier\n"
        "Bijan Robinson,ATL,RB,301.5,4.2,1\n"
        "Jets Defense,NYJ,D/ST,128,132,2\n"
    )

    assert len(result.players) == 2
    assert result.players[0].projected_points == 301.5
    assert result.players[1].position == Position.DST
    assert result.players[0].id == "bijan-robinson-atl-rb"


def test_custom_column_mapping():
    result = import_players_csv(
        "athlete,role,projection\nA Player,QB,300\n",
        {"name": "athlete", "position": "role", "projected_points": "projection"},
    )
    assert result.players[0].name == "A Player"


def test_missing_required_columns_is_structured_error():
    with pytest.raises(CsvImportError, match="missing required columns"):
        import_players_csv("Player,Team\nA Player,ABC\n")


def test_strict_mode_collects_row_issues():
    content = (
        "Player,POS,FPTS\n"
        "Valid Player,RB,200\n"
        "Bad Position,XYZ,100\n"
        "Bad Points,WR,nope\n"
    )
    with pytest.raises(CsvImportError) as caught:
        import_players_csv(content)

    assert len(caught.value.issues) == 2
    assert {issue.row for issue in caught.value.issues} == {3, 4}


def test_non_strict_mode_returns_valid_rows_and_warnings():
    result = import_players_csv(
        "Player,POS,FPTS\nValid Player,RB,200\nBad Player,XYZ,100\n",
        strict=False,
    )
    assert len(result.players) == 1
    assert len(result.warnings) == 1
