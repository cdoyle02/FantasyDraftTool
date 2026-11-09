"""Player name+team join keys for Workbook ESPN overlay."""

from draft_api.workbook.identity import (
    PlayerRef,
    normalize_player_name,
    player_join_key,
)
from draft_api.workbook.identity import normalize_team


def test_normalize_player_name_equivalent_aliases() -> None:
    assert normalize_player_name("D.J. Moore") == normalize_player_name("DJ Moore")


def test_player_join_key_team_alias() -> None:
    assert player_join_key("D.J. Moore", "WSH") == player_join_key("DJ Moore", "WAS")


def test_player_join_key_stable() -> None:
    key = player_join_key("Ja'Marr Chase", "CIN")
    assert key == "jamarr chase|CIN"


def test_player_ref_frozen() -> None:
    ref = PlayerRef(
        gsis_id=None,
        espn_player_id=1,
        display_name="Test",
        team="KC",
    )
    assert ref.espn_player_id == 1


def test_normalize_team_wsh_maps_to_was() -> None:
    assert normalize_team("WSH") == "WAS"
