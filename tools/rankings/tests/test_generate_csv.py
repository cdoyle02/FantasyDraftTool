from pathlib import Path

import pytest
from dvs_engine import import_players_csv
from generate import generate_from_inbox
from merge import csv_rows
from store import read_inbox, write_bundle

FIXTURE_INBOX = Path(__file__).resolve().parents[1] / "fixtures" / "inbox"


def test_fixture_inbox_produces_importable_six_column_csv(tmp_path: Path) -> None:
    players = generate_from_inbox(FIXTURE_INBOX)
    rows = csv_rows(players)

    assert list(rows[0]) == ["Player", "Team", "POS", "FPTS", "ADP", "Tier"]
    assert {row["POS"] for row in rows} <= {"QB", "RB", "WR", "TE", "K", "DST"}
    assert any(row["Player"] == "Jets Defense" and row["POS"] == "DST" for row in rows)
    assert any(row["Player"] == "Deep Bench Back" for row in rows)

    csv_path = tmp_path / "expert-rankings.csv"
    json_path = tmp_path / "expertRankings.json"
    write_bundle(
        players,
        json_path,
        csv_path,
        seed_version="test.1",
        experts={},
        source="fixture",
    )
    result = import_players_csv(csv_path.read_text(encoding="utf-8"))
    assert len(result.players) == len(players)
    assert result.players[0].projected_points > 0


def test_pickens_nudge_from_fixture_inbox() -> None:
    players = {player.name: player for player in generate_from_inbox(FIXTURE_INBOX)}
    # consensus 7 vs pooled 1, k=0.6 -> +3.6
    assert players["George Pickens"].projected_points == 249.8
    assert players["Justin Tucker"].adp == 250.0


def test_empty_inbox_is_a_structured_failure(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no CSV files"):
        read_inbox(tmp_path)
