import pytest

from dvs_engine import DraftState, LeagueSettings, Player, Position


@pytest.fixture
def settings() -> LeagueSettings:
    return LeagueSettings(
        team_count=4,
        roster_slots={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1, "BENCH": 2},
        user_team_id="1",
    )


@pytest.fixture
def players() -> list[Player]:
    result: list[Player] = []
    specs = {
        Position.QB: [320, 300, 280, 260, 240, 220],
        Position.RB: [290, 275, 260, 245, 230, 215, 200, 185],
        Position.WR: [285, 270, 255, 240, 225, 210, 195, 180],
        Position.TE: [230, 210, 190, 170, 150, 130],
        Position.K: [130, 125, 120, 115],
        Position.DST: [125, 120, 115, 110],
    }
    rank = 1
    for position, projections in specs.items():
        for index, points in enumerate(projections, start=1):
            result.append(
                Player(
                    id=f"{position.value.lower()}-{index}",
                    name=f"{position.value} Player {index}",
                    position=position,
                    team=f"T{index}",
                    projected_points=points,
                    adp=float(rank),
                    tier=1 if index <= 2 else 2 if index <= 4 else 3,
                )
            )
            rank += 1
    return result


@pytest.fixture
def empty_state(settings: LeagueSettings) -> DraftState:
    return DraftState(settings.team_count)
