"""Vegas implied-total adjustment for Tier 2 opportunity softness."""

from __future__ import annotations

from draft_api.implied_totals import GameLine, implied_team_totals

GAME_SCRIPT_CENTER = 22.0
GAME_SCRIPT_SPAN = 40.0
GAME_SCRIPT_MAX_DELTA = 0.15


def implied_points_for_team(game: GameLine, *, team: str) -> float | None:
    """Implied points for `team` on this game line."""
    team_key = team.strip().upper()
    fav_implied, dog_implied = implied_team_totals(total=game.total, spread=game.spread)
    if team_key == game.home_team.upper():
        return fav_implied if game.favorite_team.upper() == team_key else dog_implied
    if team_key == game.away_team.upper():
        return fav_implied if game.favorite_team.upper() == team_key else dog_implied
    return None


def find_game_line_for_matchup(
    games: list[GameLine],
    *,
    team: str,
    opponent: str,
) -> GameLine | None:
    team_key = team.strip().upper()
    opp_key = opponent.strip().upper()
    for game in games:
        home = game.home_team.upper()
        away = game.away_team.upper()
        if {team_key, opp_key} == {home, away}:
            return game
    return None


def adjust_softness_score(
    *,
    softness_score: float,
    team_implied: float | None,
    center: float = GAME_SCRIPT_CENTER,
    span: float = GAME_SCRIPT_SPAN,
    max_delta: float = GAME_SCRIPT_MAX_DELTA,
) -> tuple[float, float, bool]:
    """Return (adjusted_score, delta, applied)."""
    if team_implied is None:
        return softness_score, 0.0, False
    raw_delta = (team_implied - center) / span
    if raw_delta > max_delta:
        delta = max_delta
    elif raw_delta < -max_delta:
        delta = -max_delta
    else:
        delta = raw_delta
    adjusted = softness_score + delta
    if adjusted < 0.0:
        adjusted = 0.0
    elif adjusted > 1.0:
        adjusted = 1.0
    return adjusted, delta, True
