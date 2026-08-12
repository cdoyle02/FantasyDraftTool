from dvs_engine import (
    Position,
    RecommendationLabel,
    UserAdjustment,
    guardrail_adjustment,
    recommend,
    replacement_counts,
    replacement_levels,
    roster_need_multiplier,
    survival_probability,
    tier_cliff_urgency,
    vorp,
)


def test_replacement_levels_follow_configured_starters(players, settings):
    counts = replacement_counts(settings)
    levels = replacement_levels(players, settings)

    assert counts[Position.QB] == 4
    assert counts[Position.RB] == 6
    assert levels[Position.QB] == 260
    assert levels[Position.RB] == 215
    assert vorp(players[0], levels) == 60


def test_tier_cliff_combines_drop_and_survival(players):
    rb_one = next(player for player in players if player.id == "rb-1")
    urgent = tier_cliff_urgency(rb_one, players, 0.1)
    safe = tier_cliff_urgency(rb_one, players, 0.9)

    assert urgent > safe > 0


def test_survival_probability_declines_as_next_pick_gets_later(players):
    player = players[5]
    soon = survival_probability(player, current_pick=1, picks_until_next=2)
    later = survival_probability(player, current_pick=1, picks_until_next=20)

    assert 0 < later < soon < 1


def test_roster_need_diminishes_after_slots_fill(players, settings):
    rb_players = [player for player in players if player.position == Position.RB]
    empty = roster_need_multiplier(Position.RB, [], settings, 4)
    full = roster_need_multiplier(Position.RB, rb_players[:3], settings, 4)

    assert empty > full


def test_guardrails_suppress_early_kicker(players, settings):
    kicker = next(player for player in players if player.position == Position.K)
    assert guardrail_adjustment(kicker, 20, [], settings, 1) < -30
    assert guardrail_adjustment(kicker, 20, [], settings, settings.rounds) == 0


def test_recommendations_are_deterministic_explainable_and_adjustable(
    players, settings, empty_state
):
    baseline = recommend(players, empty_state, settings, limit=10)
    repeated = recommend(players, empty_state, settings, limit=10)
    faded = recommend(
        players,
        empty_state,
        settings,
        {"qb-1": UserAdjustment("qb-1", tag="avoid")},
        limit=10,
    )

    assert baseline == repeated
    assert baseline[0].breakdown.vorp != 0
    assert baseline[0].reasons
    assert all(item.tier_label in RecommendationLabel for item in baseline)
    assert all(item.player_id != "qb-1" for item in faded)


def test_drafted_players_are_excluded(players, settings, empty_state):
    from dvs_engine import apply_pick

    state = apply_pick(empty_state, "qb-1")
    results = recommend(players, state, settings)

    assert "qb-1" not in {result.player_id for result in results}
