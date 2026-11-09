"""Refresh the packaged SoS snapshot from live nflverse data.

Usage:
    uv run python -m draft_api.sos.refresh
    uv run python -m draft_api.sos.refresh --season 2026
"""

from __future__ import annotations

import argparse
import sys

from dataclasses import replace

from draft_api.sos.clay_roles import resolve_clay_role_index
from draft_api.sos.nflverse import load_snap_counts, load_sos_dataset, load_usage_stats
from draft_api.sos.snapshot import SnapshotError, read_packaged_snapshot, write_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh packaged SoS snapshot from nflverse")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional output path (defaults to package data/sos_{season}.json)",
    )
    args = parser.parse_args(argv)

    dataset = load_sos_dataset(args.season)
    usage_stats = load_usage_stats(args.season)
    snap_counts = load_snap_counts(args.season)
    previous_clay_roles = None
    try:
        previous_clay_roles = read_packaged_snapshot(args.season).clay_roles or None
    except SnapshotError:
        previous_clay_roles = None
    clay_roles = resolve_clay_role_index(
        args.season,
        previous_clay_roles=previous_clay_roles,
    )
    dataset = replace(
        dataset,
        usage_stats=usage_stats,
        snap_counts=snap_counts,
        clay_roles=clay_roles,
    )
    from pathlib import Path

    path = write_snapshot(dataset, Path(args.out) if args.out else None)
    print(
        f"Wrote {path} · season={dataset.season} · "
        f"games={len(dataset.games)} · ratedThroughWeek={dataset.rated_through_week} · "
        f"usageRows={len(dataset.usage_stats)} · "
        f"snapRows={len(dataset.snap_counts)} · "
        f"clayRoles={len(dataset.clay_roles)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
