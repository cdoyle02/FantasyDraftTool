"""Shared builders for canonical Formula V4 golden regression states."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dvs_engine import (
    DraftState,
    FormulaParams,
    LeagueSettings,
    Pick,
    Player,
    Position,
    apply_pick,
    as_jsonable,
    recommend,
    recommend_v4,
    team_on_clock,
)
from dvs_engine.browser import recommendation_json

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "v4_golden"

TWELVE = {
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

V5_ONLY_BREAKDOWN_KEYS = frozenset(
    {
        "negative_vorp_adjustment",
        "raw_handcuff_bonus",
        "adjusted_handcuff_bonus",
        "own_handcuff_league_multiplier",
        "own_handcuff_count",
        "own_handcuff_count_multiplier",
        "bench_balance_adjustment",
        "usable_rb_depth",
        "usable_wr_depth",
        "roster_risk_score",
        "pre_reliability_score",
        "reliability_adjustment",
        "v5_policy_strength",
    }
)

V5_ONLY_PARAM_KEYS = frozenset(
    {
        "v5_policy_strength",
        "negative_vorp_bench_weight",
        "negative_vorp_bench_cap",
        "negative_vorp_starter_damp",
        "own_handcuff_factor_8_team",
        "own_handcuff_factor_10_team",
        "own_handcuff_factor_12_team",
        "own_handcuff_factor_14_team",
        "own_handcuff_second_multiplier",
        "own_handcuff_third_multiplier",
        "own_handcuff_fourth_plus_multiplier",
        "bench_balance_band_half_width",
        "bench_balance_usable_vorp_floor_ratio",
        "bench_balance_reserve_slots",
        "bench_balance_max_adjustment",
        "reliability_weight_max",
        "reliability_close_score_threshold",
        "reliability_target_risk",
        "reliability_risk_span",
        "reliability_min_known_players",
        "reliability_flex_weight",
        "reliability_reserve_weight",
        "reliability_reserve_slots",
    }
)


def _league(**overrides) -> LeagueSettings:
    base = {
        "team_count": 12,
        "roster_slots": TWELVE,
        "user_team_id": "1",
        "formula_params": FormulaParams(),
    }
    base.update(overrides)
    return LeagueSettings(**base)


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


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def recommendation_payload(
    name: str,
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    limit: int = 20,
) -> dict[str, Any]:
    results = recommend_v4(list(players), state, settings, limit=limit)
    return {
        "name": name,
        "configuration": {
            "formulaVersion": settings.formula_params.formula_version,
            "oneTurnSims": settings.formula_params.one_turn_sims,
            "simulationSeed": settings.formula_params.sim_seed,
            "formulaParams": as_jsonable(settings.formula_params),
        },
        "recommendations": as_jsonable(results),
        "count": len(results),
    }


def browser_payload(
    players: Sequence[Player],
    state: DraftState,
    settings: LeagueSettings,
    limit: int = 20,
) -> dict[str, Any]:
    payload = {
        "players": [as_jsonable(player) for player in players],
        "settings": {
            "teamCount": settings.team_count,
            "rosterSlots": dict(settings.roster_slots),
            "scoringFormat": settings.scoring_format,
            "draftType": "snake",
            "leagueType": settings.league_type,
            "userTeamId": settings.user_team_id,
            "formulaVersion": settings.formula_params.formula_version,
            "keeperSlots": settings.keeper_slots,
            "irSlots": settings.ir_slots,
        },
        "draftState": {
            "teamCount": state.team_count,
            "pickHistory": [
                {
                    "pickNumber": pick.pick_number,
                    "teamId": pick.team_id,
                    "playerId": pick.player_id,
                }
                for pick in state.pick_history
            ],
            "reservedRosters": {
                team: list(player_ids)
                for team, player_ids in state.reserved_rosters.items()
            },
        },
        "adjustments": [],
        "limit": limit,
    }
    return json.loads(recommendation_json(json.dumps(payload)))


def build_golden_states() -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}

    # 1. Early round
    early_pool = [
        Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
        Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
        Player("rb-2", "RB2", Position.RB, projected_points=240, adp=30.0, tier=2),
        Player("wr-2", "WR2", Position.WR, projected_points=235, adp=31.0, tier=2),
    ]
    early_league = _league(
        team_count=4,
        roster_slots={
            "QB": 0,
            "RB": 1,
            "WR": 1,
            "TE": 0,
            "FLEX": 0,
            "BENCH": 0,
            "K": 0,
            "DST": 0,
        },
    )
    early_state = DraftState(team_count=4)
    states["early_round"] = recommendation_payload(
        "early_round", early_pool, early_state, early_league, limit=4
    )

    # 2. Mid round
    mid_pool = _fillers(220) + [
        Player("qb-1", "QB1", Position.QB, projected_points=280, adp=55.0, tier=2),
        Player("rb-mid", "RB Mid", Position.RB, projected_points=240, adp=60.0, tier=2),
        Player("wr-mid", "WR Mid", Position.WR, projected_points=230, adp=61.0, tier=2),
    ]
    mid_league = _league()
    mid_state = _advance_user_picks(
        mid_pool,
        ("qb-1", "rb-mid", "wr-mid"),
        team_count=12,
    )
    states["mid_round"] = recommendation_payload(
        "mid_round", mid_pool, mid_state, mid_league, limit=10
    )

    # 3. Starters nearly complete
    starter_roster = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
    ]
    near_pool = _fillers(220) + [
        Player("flex-a", "Flex A", Position.RB, projected_points=180, adp=100.0, tier=3),
        Player("flex-b", "Flex B", Position.WR, projected_points=175, adp=101.0, tier=3),
    ]
    near_league = _league()
    near_state = DraftState(
        team_count=12,
        pick_history=tuple(
            Pick(pick, team_on_clock(pick, 12), f"ghost-{pick}") for pick in range(1, 72)
        ),
        reserved_rosters={"1": tuple(p.id for p in starter_roster)},
    )
    states["starters_nearly_complete"] = recommendation_payload(
        "starters_nearly_complete", near_pool, near_state, near_league, limit=10
    )

    # 4. Late round
    late_roster = [
        Player("qb", "QB", Position.QB, projected_points=280),
        Player("rb1", "RB1", Position.RB, projected_points=250),
        Player("rb2", "RB2", Position.RB, projected_points=240),
        Player("wr1", "WR1", Position.WR, projected_points=230),
        Player("wr2", "WR2", Position.WR, projected_points=220),
        Player("te", "TE", Position.TE, projected_points=200),
        Player("rb3", "RB3", Position.RB, projected_points=180),
        Player("wr3", "WR3", Position.WR, projected_points=170),
        Player("rb4", "RB4", Position.RB, projected_points=160),
        Player("wr4", "WR4", Position.WR, projected_points=150),
        Player("rb5", "RB5", Position.RB, projected_points=140),
        Player("wr5", "WR5", Position.WR, projected_points=130),
        Player("rb6", "RB6", Position.RB, projected_points=120),
    ]
    sleeper = Player(
        "rb-sleep",
        "Sleeper RB",
        Position.RB,
        projected_points=55,
        adp=180.0,
        tier=5,
        upside_score=9.0,
        is_rookie=True,
    )
    late_pool = [sleeper] + _fillers(40)
    late_league = _league()
    late_state = DraftState(
        team_count=12,
        pick_history=tuple(
            Pick(pick, team_on_clock(pick, 12), f"ghost-{pick}") for pick in range(1, 169)
        ),
        reserved_rosters={"1": tuple(p.id for p in late_roster)},
    )
    states["late_round"] = recommendation_payload(
        "late_round", late_pool, late_state, late_league, limit=10
    )

    # 5. Own-handcuff scenario (metadata present, late phase)
    hc_starter = Player(
        "rb1",
        "Starter",
        Position.RB,
        team="LV",
        projected_points=250,
        depth_chart_rank=1,
        depth_chart_source="official",
    )
    hc_backup = Player(
        "rb2",
        "Backup",
        Position.RB,
        team="LV",
        projected_points=80,
        adp=200.0,
        tier=5,
        depth_chart_rank=2,
        depth_chart_source="official",
        risk_score=6.0,
    )
    hc_pool = [hc_backup] + _fillers(40)
    hc_league = _league(ir_slots=1)
    hc_state = DraftState(
        team_count=12,
        pick_history=tuple(Pick(i, "2", f"g-{i}") for i in range(1, 169)),
        reserved_rosters={"1": ("rb1",)},
    )
    hc_settings = LeagueSettings(
        team_count=12,
        roster_slots=TWELVE,
        user_team_id="1",
        ir_slots=1,
        formula_params=FormulaParams(),
    )
    hc_settings_roster = [hc_starter]
    # reserved roster only has id; map for recommend
    hc_full_pool = [hc_starter, hc_backup, *_fillers(40)]
    states["own_handcuff"] = recommendation_payload(
        "own_handcuff", hc_full_pool, hc_state, hc_settings, limit=5
    )

    # 6. Special teams eligibility window
    st_roster = [
        Player(f"p-{i}", f"P{i}", Position.WR, projected_points=100 - i, adp=10 + i)
        for i in range(13)
    ]
    dst = Player("dst-1", "DST1", Position.DST, projected_points=125, adp=150.0)
    wr_late = Player("wr-late", "WR Late", Position.WR, projected_points=50, adp=160.0)
    k = Player("k-1", "K1", Position.K, projected_points=130, adp=151.0)
    st_pool = [dst, wr_late, k]
    st_league = _league()
    penultimate = (st_league.rounds - 1) * 12 + 1
    st_state = DraftState(
        team_count=12,
        pick_history=tuple(Pick(p, team_on_clock(p, 12), f"g-{p}") for p in range(1, penultimate)),
        reserved_rosters={"1": tuple(p.id for p in st_roster)},
    )
    states["special_teams_window"] = recommendation_payload(
        "special_teams_window", st_pool, st_state, st_league, limit=5
    )

    return states


def write_golden_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in build_golden_states().items():
        path = FIXTURES_DIR / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    browser = browser_payload(
        [
            Player("rb-1", "RB1", Position.RB, projected_points=280, adp=1.0, tier=1),
            Player("wr-1", "WR1", Position.WR, projected_points=270, adp=2.0, tier=1),
        ],
        DraftState(team_count=2),
        _league(
            team_count=2,
            roster_slots={
                "QB": 0,
                "RB": 1,
                "WR": 1,
                "TE": 0,
                "FLEX": 0,
                "BENCH": 0,
                "K": 0,
                "DST": 0,
            },
        ),
        limit=2,
    )
    (FIXTURES_DIR / "browser_early.json").write_text(
        json.dumps(browser, indent=2) + "\n", encoding="utf-8"
    )


def assert_no_v5_keys(obj: Mapping[str, Any]) -> None:
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            assert key not in V5_ONLY_BREAKDOWN_KEYS
            assert key not in V5_ONLY_PARAM_KEYS
            assert_no_v5_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (Mapping, list)):
                assert_no_v5_keys(item)


def project_v4_breakdown(breakdown: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in breakdown.items() if k not in V5_ONLY_BREAKDOWN_KEYS}


if __name__ == "__main__":
    write_golden_fixtures()
    print(f"Wrote fixtures to {FIXTURES_DIR}")
