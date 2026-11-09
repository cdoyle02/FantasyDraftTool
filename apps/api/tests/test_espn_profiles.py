"""League-aware ESPN cookie profile resolution."""

from __future__ import annotations

import pytest

from draft_api.espn_available_dst import EspnAvailableError, espn_credentials_from_env
from draft_api.espn_profiles import resolve_espn_profile


def test_resolve_gwb_to_katie():
    assert resolve_espn_profile("1216398267") == "katie"


def test_resolve_fff_to_michael():
    assert resolve_espn_profile("169429") == "michael"


def test_resolve_missing_league_to_michael():
    assert resolve_espn_profile(None) == "michael"
    assert resolve_espn_profile("") == "michael"
    assert resolve_espn_profile("999999") == "michael"


def test_resolve_override_wins():
    assert resolve_espn_profile("1216398267", espn_profile="michael") == "michael"
    assert resolve_espn_profile("169429", espn_profile="katie") == "katie"


def test_resolve_invalid_override():
    with pytest.raises(ValueError, match="espn_profile"):
        resolve_espn_profile("169429", espn_profile="nope")


def test_credentials_select_katie_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ESPN_S2", "michael-s2")
    monkeypatch.setenv("ESPN_SWID", "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}")
    monkeypatch.setenv("ESPN_S2_KATIE", "katie-s2")
    monkeypatch.setenv("ESPN_SWID_KATIE", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    monkeypatch.setenv("ESPN_SEASON", "2026")

    s2, swid, season = espn_credentials_from_env(league_id="1216398267")
    assert s2 == "katie-s2"
    assert swid == "{bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb}"
    assert season == 2026


def test_credentials_select_michael_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ESPN_S2", "michael-s2")
    monkeypatch.setenv("ESPN_SWID", "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}")
    monkeypatch.setenv("ESPN_S2_KATIE", "katie-s2")
    monkeypatch.setenv("ESPN_SWID_KATIE", "{bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb}")

    s2, swid, _ = espn_credentials_from_env(league_id="169429")
    assert s2 == "michael-s2"
    assert swid == "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}"


def test_credentials_override_profile(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ESPN_S2", "michael-s2")
    monkeypatch.setenv("ESPN_SWID", "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}")
    monkeypatch.setenv("ESPN_S2_KATIE", "katie-s2")
    monkeypatch.setenv("ESPN_SWID_KATIE", "{bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb}")

    s2, _, _ = espn_credentials_from_env(league_id="1216398267", espn_profile="michael")
    assert s2 == "michael-s2"


def test_credentials_invalid_profile_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ESPN_S2", "michael-s2")
    monkeypatch.setenv("ESPN_SWID", "{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}")
    with pytest.raises(EspnAvailableError, match="espn_profile"):
        espn_credentials_from_env(espn_profile="nope")
