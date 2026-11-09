"""Refresh the packaged Workbook snapshot from live nflverse data.

Usage:
    uv run python -m draft_api.workbook.refresh
    uv run python -m draft_api.workbook.refresh --season 2026
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from draft_api.workbook.nflverse import load_workbook_dataset
from draft_api.workbook.snapshot import (
    SnapshotError,
    dataset_from_dict,
    snapshot_path_for_write,
    write_snapshot,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh packaged Workbook snapshot from nflverse"
    )
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional output path (defaults to package data/workbook_{season}.json)",
    )
    args = parser.parse_args(argv)

    path = Path(args.out) if args.out else snapshot_path_for_write(args.season)
    previous_clay_roles = None
    if path.exists():
        try:
            previous_clay_roles = dataset_from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            ).clay_roles or None
        except (SnapshotError, json.JSONDecodeError, OSError):
            previous_clay_roles = None

    dataset = load_workbook_dataset(
        args.season, previous_clay_roles=previous_clay_roles
    )
    write_snapshot(path, dataset)
    print(
        f"Wrote {path} · season={dataset.season} · "
        f"teams={len(dataset.teams)} · drives={len(dataset.drives)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
