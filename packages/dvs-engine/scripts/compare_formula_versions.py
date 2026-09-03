#!/usr/bin/env python3
"""Replay schema-v2 draft evaluation exports through Formula V4 and V5."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from dataclasses import replace

from dvs_engine import (
    DraftState,
    FormulaParams,
    Pick,
    Player,
    Position,
    UserAdjustment,
    V5FormulaParams,
    recommend_v4,
    recommend_v5,
    settings_from_dict,
)


def _load_export(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _player_from_export(data: dict[str, Any]) -> Player:
    position = Position[data["position"]]
    return Player(
        id=data["id"],
        name=data["name"],
        position=position,
        team=data.get("team", ""),
        projected_points=float(data.get("projectedPoints", data.get("projected_points", 0))),
        adp=data.get("adp"),
        tier=int(data.get("tier", 1)),
        depth_chart_rank=data.get("depthChartRank", data.get("depth_chart_rank")),
        depth_chart_source=data.get("depthChartSource", data.get("depth_chart_source")),
        upside_score=data.get("upsideScore", data.get("upside_score")),
        risk_score=data.get("riskScore", data.get("risk_score")),
        is_rookie=data.get("isRookie", data.get("is_rookie", False)),
        is_breakout=data.get("isBreakout", data.get("is_breakout", False)),
        ir_eligible=data.get("irEligible", data.get("ir_eligible", False)),
    )


def _state_from_record(record: dict[str, Any], settings) -> DraftState:
    board = record.get("boardState", {})
    picks = board.get("picks", [])
    keepers = board.get("keepers", [])
    pick_history = tuple(
        Pick(
            int(pick["pickNumber"]),
            str(pick["teamId"]),
            pick["playerId"],
        )
        for pick in picks
    )
    reserved: dict[str, tuple[str, ...]] = {}
    for keeper in keepers:
        team = str(keeper["teamId"])
        reserved.setdefault(team, ())
        reserved[team] = (*reserved.get(team, ()), keeper["playerId"])
    return DraftState(settings.team_count, pick_history=pick_history, reserved_rosters=reserved)


def _adjustments_from_record(record: dict[str, Any]) -> dict[str, UserAdjustment]:
    board = record.get("boardState", {})
    result: dict[str, UserAdjustment] = {}
    for item in board.get("adjustments", []):
        adjustment = UserAdjustment(
            player_id=item["playerId"],
            points_delta=float(item.get("pointsDelta", 0)),
            tier_override=item.get("tierOverride"),
            tag=item.get("tag"),
            note=item.get("note"),
        )
        result[adjustment.player_id] = adjustment
    return result


def _settings_from_record(export: dict[str, Any], record: dict[str, Any]):
    board = record.get("boardState", {})
    settings_payload = board.get("settings", export.get("settings", {}))
    return settings_from_dict(settings_payload)


def _compare_lists(v4_results, v5_results) -> list[dict[str, Any]]:
    v4_by_id = {item.player_id: item for item in v4_results}
    v5_by_id = {item.player_id: item for item in v5_results}
    rows: list[dict[str, Any]] = []
    for rank, v4_item in enumerate(v4_results, start=1):
        v5_item = v5_by_id.get(v4_item.player_id)
        v5_rank = next(
            (index for index, item in enumerate(v5_results, start=1) if item.player_id == v4_item.player_id),
            None,
        )
        rows.append(
            {
                "playerId": v4_item.player_id,
                "playerName": v4_item.player_name,
                "v4Rank": rank,
                "v5Rank": v5_rank,
                "rankDelta": None if v5_rank is None else v5_rank - rank,
                "v4Score": v4_item.dvs_score,
                "v5Score": None if v5_item is None else v5_item.dvs_score,
                "scoreDelta": None if v5_item is None else round(v5_item.dvs_score - v4_item.dvs_score, 4),
            }
        )
    for player_id, v5_item in v5_by_id.items():
        if player_id in v4_by_id:
            continue
        v5_rank = next(
            index for index, item in enumerate(v5_results, start=1) if item.player_id == player_id
        )
        rows.append(
            {
                "playerId": player_id,
                "playerName": v5_item.player_name,
                "v4Rank": None,
                "v5Rank": v5_rank,
                "rankDelta": None,
                "v4Score": None,
                "v5Score": v5_item.dvs_score,
                "scoreDelta": None,
            }
        )
    return rows


def replay_export(export: dict[str, Any]) -> dict[str, Any]:
    records = export.get("evaluationRecords", export.get("records", []))
    comparisons: list[dict[str, Any]] = []
    for record in records:
        if record.get("status") != "active":
            continue
        settings = _settings_from_record(export, record)
        v4_settings = replace(settings, formula_params=FormulaParams())
        v5_settings = replace(settings, formula_params=V5FormulaParams())
        players = [_player_from_export(player) for player in record.get("boardState", {}).get("players", export.get("players", []))]
        state = _state_from_record(record, settings)
        adjustments = _adjustments_from_record(record)
        v4_results = recommend_v4(players, state, v4_settings, adjustments=adjustments, limit=20)
        v5_results = recommend_v5(players, state, v5_settings, adjustments=adjustments, limit=20)
        comparisons.append(
            {
                "sourceRecordId": record.get("id"),
                "pickNumber": record.get("pickNumber"),
                "sourceFormulaVersion": record.get("recommendationGeneration", {}).get("formulaVersion"),
                "rows": _compare_lists(v4_results, v5_results),
            }
        )
    return {
        "schema": "formula-version-comparison-v1",
        "sourceExportSchema": export.get("schemaVersion"),
        "recordCount": len(comparisons),
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="Schema-v2 draft evaluation export JSON")
    parser.add_argument("--json-out", type=Path, help="Write comparison JSON")
    parser.add_argument("--csv-out", type=Path, help="Write flattened CSV")
    args = parser.parse_args()

    export = _load_export(args.export)
    comparison = replay_export(export)

    if args.json_out:
        args.json_out.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(comparison, indent=2))

    if args.csv_out:
        with args.csv_out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "sourceRecordId",
                    "pickNumber",
                    "playerId",
                    "playerName",
                    "v4Rank",
                    "v5Rank",
                    "rankDelta",
                    "v4Score",
                    "v5Score",
                    "scoreDelta",
                ],
            )
            writer.writeheader()
            for block in comparison["comparisons"]:
                for row in block["rows"]:
                    writer.writerow(
                        {
                            "sourceRecordId": block["sourceRecordId"],
                            "pickNumber": block["pickNumber"],
                            **row,
                        }
                    )


if __name__ == "__main__":
    main()
