from datetime import datetime, timezone

from draft_api.implied_totals import GameLine
from draft_api.odds.cache import TtlCache
from draft_api.odds.fake import FakeOddsProvider
from draft_api.odds.the_odds_api import TheOddsApiProvider, consensus_line, team_abbrev


def test_fake_provider_returns_supplied_games():
    game = GameLine(
        home_team="KC",
        away_team="LV",
        commence_time=datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc),
        spread=-7.0,
        total=42.0,
        favorite_team="KC",
        underdog_team="LV",
        bookmaker="consensus",
    )
    provider = FakeOddsProvider([game])
    assert provider.fetch_nfl_odds() == [game]


def test_ttl_cache_expires():
    cache: TtlCache[str] = TtlCache(ttl_seconds=0.01)
    cache.set("hello")
    assert cache.get() == "hello"
    import time

    time.sleep(0.02)
    assert cache.get() is None


def test_team_abbrev_maps_known_names():
    assert team_abbrev("Kansas City Chiefs") == "KC"
    assert team_abbrev("Unknown FC") == "Unknown FC"


def test_consensus_line_averages_draftkings_and_fanduel():
    event = {
        "home_team": "Kansas City Chiefs",
        "away_team": "Las Vegas Raiders",
        "commence_time": "2026-09-13T17:00:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Kansas City Chiefs", "point": -9.5},
                            {"name": "Las Vegas Raiders", "point": 9.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 41.0},
                            {"name": "Under", "point": 41.0},
                        ],
                    },
                ],
            },
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Kansas City Chiefs", "point": -10.5},
                            {"name": "Las Vegas Raiders", "point": 10.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 42.0},
                            {"name": "Under", "point": 42.0},
                        ],
                    },
                ],
            },
        ],
    }
    line = consensus_line(event)
    assert line is not None
    assert line.home_team == "KC"
    assert line.away_team == "LV"
    assert line.spread == -10.0
    assert line.total == 41.5
    assert line.favorite_team == "KC"
    assert line.underdog_team == "LV"
    assert line.bookmaker == "consensus"


def test_the_odds_api_provider_parses_http_payload():
    payload = b"""[
      {
        "home_team": "Buffalo Bills",
        "away_team": "Miami Dolphins",
        "commence_time": "2026-09-13T20:00:00Z",
        "bookmakers": [
          {
            "key": "draftkings",
            "markets": [
              {
                "key": "spreads",
                "outcomes": [
                  {"name": "Buffalo Bills", "point": -3.5},
                  {"name": "Miami Dolphins", "point": 3.5}
                ]
              },
              {
                "key": "totals",
                "outcomes": [
                  {"name": "Over", "point": 47.5},
                  {"name": "Under", "point": 47.5}
                ]
              }
            ]
          }
        ]
      }
    ]"""

    def fake_get(url: str) -> bytes:
        assert "americanfootball_nfl" in url
        assert "apiKey=test-key" in url
        return payload

    provider = TheOddsApiProvider("test-key", http_get=fake_get)
    games = provider.fetch_nfl_odds()
    assert len(games) == 1
    assert games[0].favorite_team == "BUF"
    assert games[0].spread == -3.5
    assert games[0].total == 47.5
