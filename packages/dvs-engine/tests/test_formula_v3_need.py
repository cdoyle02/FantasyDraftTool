import pytest
from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Player,
    Position,
    apply_pick,
    guardrail_adjustment,
    recommend,
    replacement_levels,
    roster_shape_need,
    team_on_clock,
)
from dvs_engine.formula import position_caps_map, starter_capacity, depth_target
from dvs_engine.lineup import marginal_value

TWELVE_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "SUPERFLEX": 0,
    "BENCH": 6,
    "K": 1,
    "DST": 1,
}


def _twelve_team(params: FormulaParams | None = None) -> LeagueSettings:
    return LeagueSettings(
        team_count=12,
        roster_slots=TWELVE_SLOTS,
        user_team_id="1",
        formula_params=params or FormulaParams(formula_version=3),
    )


def _fillers(count: int) -> list[Player]:
    return [
        Player(
            id=f"fill-{index}",
            name=f"Filler {index}",
            position=Position.WR if index % 2 == 0 else Position.RB,
            projected_points=45.0,
            adp=400.0 + index,
            tier=5,
        )
        for index in range(count)
    ]


def _advance_user_picks(
    pool: list[Player],
    user_ids: tuple[str, ...],
    team_count: int = 12,
    user_team_id: str = "1",
) -> DraftState:
    filler_ids = [player.id for player in pool if player.id.startswith("fill-")]
    filler_index = 0
    used: set[str] = set()
    state = DraftState(team_count)
    user_index = 0
    while user_index < len(user_ids):
        if team_on_clock(state.current_pick, team_count) == user_team_id:
            state = apply_pick(state, user_ids[user_index])
            used.add(user_ids[user_index])
            user_index += 1
        else:
            while filler_ids[filler_index] in used:
                filler_index += 1
            state = apply_pick(state, filler_ids[filler_index])
            used.add(filler_ids[filler_index])
            filler_index += 1
    while team_on_clock(state.current_pick, team_count) != user_team_id:
        while filler_ids[filler_index] in used:
            filler_index += 1
        state = apply_pick(state, filler_ids[filler_index])
        used.add(filler_ids[filler_index])
        filler_index += 1
    return state


def _scenario_pool(*featured: Player) -> list[Player]:
    return [*featured, *_fillers(220)]


def test_depth_targets_match_default_league_shape():
    settings = _twelve_team()
    assert starter_capacity(Position.TE, settings) == pytest.approx(1.0)
    assert depth_target(Position.TE, settings) == pytest.approx(1.0)
    assert depth_target(Position.QB, settings) == pytest.approx(1.0)
    assert depth_target(Position.RB, settings) == pytest.approx(5.45)
    assert depth_target(Position.WR, settings) == pytest.approx(5.45)


def test_need_multiplier_stays_within_v3_bounds():
    settings = _twelve_team()
    params = settings.formula_params
    for position in (Position.QB, Position.RB, Position.WR, Position.TE):
        for filled in range(0, 8):
            roster = [
                Player(f"{position.value}-{index}", f"{position.value}{index}", position)
                for index in range(filled)
            ]
            for round_number in (1, 4, 8, 14):
                need = roster_shape_need(position, roster, settings, round_number)
                assert params.need_v3_floor <= need <= params.need_v3_ceiling


def test_wr_in_round_one_makes_comparable_rb_outrank_wr_in_round_two():
    settings = _twelve_team()
    wr1 = Player("wr-1", "First WR", Position.WR, projected_points=280, adp=1.0, tier=1)
    cmp_rb = Player("cmp-rb", "Cmp RB", Position.RB, projected_points=240, adp=25.0, tier=1)
    cmp_wr = Player("cmp-wr", "Cmp WR", Position.WR, projected_points=240, adp=25.0, tier=1)
    pool = _scenario_pool(wr1, cmp_rb, cmp_wr)
    state = _advance_user_picks(pool, ("wr-1",))
    results = recommend(pool, state, settings, limit=20)
    ranks = {item.player_id: index for index, item in enumerate(results)}
    assert ranks["cmp-rb"] < ranks["cmp-wr"]
    rb = next(item for item in results if item.player_id == "cmp-rb")
    wr = next(item for item in results if item.player_id == "cmp-wr")
    assert rb.breakdown.need_multiplier > wr.breakdown.need_multiplier


def test_two_rbs_and_one_wr_prefer_the_next_wr():
    settings = _twelve_team()
    rb1 = Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1)
    rb2 = Player("rb-2", "RB2", Position.RB, projected_points=270, adp=24.0, tier=1)
    wr1 = Player("wr-1", "WR1", Position.WR, projected_points=265, adp=25.0, tier=1)
    cmp_rb = Player("cmp-rb", "Cmp RB", Position.RB, projected_points=230, adp=40.0, tier=2)
    cmp_wr = Player("cmp-wr", "Cmp WR", Position.WR, projected_points=230, adp=40.0, tier=2)
    pool = _scenario_pool(rb1, rb2, wr1, cmp_rb, cmp_wr)
    state = _advance_user_picks(pool, ("rb-1", "rb-2", "wr-1"))
    results = recommend(pool, state, settings, limit=20)
    ranks = {item.player_id: index for index, item in enumerate(results)}
    assert ranks["cmp-wr"] < ranks["cmp-rb"]


def test_bowers_case_does_not_recommend_second_te():
    settings = _twelve_team()
    wr1 = Player("wr-1", "First WR", Position.WR, projected_points=280, adp=1.0, tier=1)
    bowers = Player("te-bowers", "Brock Bowers", Position.TE, projected_points=260, adp=24.0, tier=1)
    te2 = Player("te-warren", "Tyler Warren", Position.TE, projected_points=255, adp=25.0, tier=1)
    te3 = Player("te-3", "TE3", Position.TE, projected_points=240, adp=26.0, tier=1)
    cmp_rb = Player("cmp-rb", "Cmp RB", Position.RB, projected_points=230, adp=30.0, tier=1)
    cmp_wr = Player("cmp-wr", "Cmp WR", Position.WR, projected_points=230, adp=31.0, tier=1)
    pool = _scenario_pool(wr1, bowers, te2, te3, cmp_rb, cmp_wr)
    state = _advance_user_picks(pool, ("wr-1", "te-bowers"))
    results = recommend(pool, state, settings, limit=len(pool))
    top_three = [item.player_id for item in results[:3]]
    assert "te-warren" not in top_three
    assert "te-3" not in top_three
    te_result = next(item for item in results if item.player_id == "te-warren")
    rb_result = next(item for item in results if item.player_id == "cmp-rb")
    wr_result = next(item for item in results if item.player_id == "cmp-wr")
    assert te_result.dvs_score < rb_result.dvs_score
    assert te_result.dvs_score < wr_result.dvs_score
    assert te_result.breakdown.guardrail_adjustment <= -72.0
    assert "roster already has a TE" in te_result.reasons


def test_second_qb_buried_mid_draft_and_lighter_late():
    settings = _twelve_team()
    qb1 = Player("qb-1", "QB1", Position.QB, projected_points=320, adp=20.0, tier=1)
    qb2 = Player("qb-2", "QB2", Position.QB, projected_points=300, adp=80.0, tier=2)
    rb1 = Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1)
    wr1 = Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1)
    extra = [
        Player(f"rb-x{index}", f"RBx{index}", Position.RB, projected_points=200 - index, adp=50.0 + index, tier=2)
        for index in range(10)
    ]
    extra += [
        Player(f"wr-x{index}", f"WRx{index}", Position.WR, projected_points=195 - index, adp=60.0 + index, tier=2)
        for index in range(10)
    ]
    pool = _scenario_pool(qb1, qb2, rb1, wr1, *extra)

    mid_ids = ("rb-1", "wr-1", "qb-1", "rb-x0", "wr-x0")
    mid_state = _advance_user_picks(pool, mid_ids)
    mid_round = (mid_state.current_pick - 1) // 12 + 1
    assert mid_round < 12
    mid_results = recommend(pool, mid_state, settings, limit=len(pool))
    mid_qb = next(item for item in mid_results if item.player_id == "qb-2")
    assert mid_qb.breakdown.guardrail_adjustment <= -72.0
    assert all(item.player_id != "qb-2" for item in mid_results[:5])

    late_ids = (
        "rb-1",
        "wr-1",
        "qb-1",
        "rb-x0",
        "wr-x0",
        "rb-x1",
        "wr-x1",
        "rb-x2",
        "wr-x2",
        "rb-x3",
        "wr-x3",
        "rb-x4",
    )
    late_state = _advance_user_picks(pool, late_ids)
    late_round = (late_state.current_pick - 1) // 12 + 1
    assert late_round > settings.rounds - settings.formula_params.backup_qb_final_rounds
    late_results = recommend(pool, late_state, settings, limit=len(pool))
    late_qb = next(item for item in late_results if item.player_id == "qb-2")
    assert late_qb.breakdown.guardrail_adjustment > mid_qb.breakdown.guardrail_adjustment
    assert late_qb.breakdown.guardrail_adjustment > -30.0
    assert late_qb.dvs_score > mid_qb.dvs_score
    assert "backup QB only late" in late_qb.reasons


def test_value_dominance_override_floors_need_at_one():
    settings = _twelve_team()
    rbs = [
        Player(f"rb-{index}", f"RB{index}", Position.RB, projected_points=220 - index, adp=float(index + 1), tier=2)
        for index in range(6)
    ]
    wrs = [
        Player(f"wr-{index}", f"WR{index}", Position.WR, projected_points=215 - index, adp=float(index + 10), tier=2)
        for index in range(3)
    ]
    qb1 = Player("qb-1", "QB1", Position.QB, projected_points=300, adp=50.0, tier=2)
    te1 = Player("te-1", "TE1", Position.TE, projected_points=200, adp=51.0, tier=2)
    elite = Player("rb-elite", "Elite RB", Position.RB, projected_points=420, adp=3.0, tier=1)
    needed_wr = Player("wr-needed", "Needed WR", Position.WR, projected_points=180, adp=40.0, tier=2)
    pool = _scenario_pool(*rbs, *wrs, qb1, te1, elite, needed_wr)
    user_ids = tuple(player.id for player in (*rbs, *wrs, qb1, te1))
    state = _advance_user_picks(pool, user_ids)
    results = recommend(pool, state, settings, limit=10)
    top = results[0]
    assert top.player_id == "rb-elite"
    assert top.breakdown.need_multiplier == pytest.approx(1.0)
    assert "elite value overrides roster need" in top.reasons


def test_second_te_cannot_claim_flex_at_full_surplus():
    settings = _twelve_team()
    params = settings.formula_params
    caps = position_caps_map(settings)
    levels = replacement_levels([], settings)
    levels = {
        **levels,
        Position.RB: 150.0,
        Position.WR: 150.0,
        Position.TE: 150.0,
    }
    te1 = Player("te-1", "TE1", Position.TE, projected_points=250)
    te2 = Player("te-2", "TE2", Position.TE, projected_points=250)
    rb1 = Player("rb-1", "RB1", Position.RB, projected_points=250)
    rb2 = Player("rb-2", "RB2", Position.RB, projected_points=250)
    rb3 = Player("rb-3", "RB3", Position.RB, projected_points=250)
    roster = [te1, rb1, rb2]
    te_marginal = marginal_value(te2, roster, settings, levels, params, caps)
    rb_marginal = marginal_value(rb3, roster, settings, levels, params, caps)
    uncapped = marginal_value(te2, roster, settings, levels, params, None)
    assert te_marginal < rb_marginal
    assert te_marginal == pytest.approx(0.35 * 100.0)
    assert rb_marginal == pytest.approx(100.0)
    assert uncapped > te_marginal


def test_v2_formula_version_keeps_need_neutral(players, empty_state):
    v2 = LeagueSettings(
        team_count=4,
        roster_slots={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1, "BENCH": 2},
        user_team_id="1",
        formula_params=FormulaParams(formula_version=2),
    )
    results = recommend(players, empty_state, v2, limit=5)
    top = results[0]
    params = v2.formula_params
    expected = (
        top.breakdown.marginal_value
        + params.wait_loss_weight * top.breakdown.wait_loss
        + top.breakdown.guardrail_adjustment
    )
    assert top.dvs_score == pytest.approx(expected, abs=0.01)
    assert top.breakdown.need_multiplier == 1.0


def test_te_cap_guardrail_is_value_independent():
    settings = _twelve_team()
    te = Player("te-2", "TE2", Position.TE, projected_points=300)
    rostered = [Player("te-1", "TE1", Position.TE, projected_points=280)]
    assert guardrail_adjustment(te, 80, rostered, settings, 3) <= -72.0
    assert guardrail_adjustment(te, 80, [], settings, 3) == 0.0
