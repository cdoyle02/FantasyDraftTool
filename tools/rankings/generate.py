"""Generate the committed expert-pooled rankings seed.

Usage:
  uv run python tools/rankings/generate.py
  uv run python tools/rankings/generate.py --inbox
  uv run python tools/rankings/generate.py --from-data

API key (never shipped in the app): FANTASYPROS_API_KEY
Without a key, drop FantasyPros CSVs in tools/rankings/inbox/ or use --from-data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from espn_adp import load_espn_adp
from fetch import FantasyProsError, api_key_from_env, fetch_inputs
from merge import AdpRow, MergeConfig, SeedPlayer, merge_rankings
from store import load_config, read_inbox, write_bundle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_JSON = REPO / "apps" / "web" / "src" / "data" / "expertRankings.json"
DEFAULT_CSV = HERE / "out" / "expert-rankings.csv"
DEFAULT_CONFIG = HERE / "experts.json"
DEFAULT_INBOX = HERE / "inbox"
SEED_VERSION = "2026.4"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the expert-pooled rankings seed")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--inbox-dir", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--inbox",
        action="store_true",
        help="Use inbox CSVs even if an API key is set",
    )
    parser.add_argument(
        "--from-data",
        action="store_true",
        help="Use the bundled 2026 board in data.py (no live FantasyPros fetch)",
    )
    parser.add_argument("--seed-version", default=SEED_VERSION)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    merge_config = MergeConfig(
        k=float(config.get("k", 0.6)),
        nudge_clamp=float(config.get("nudgeClamp", 8.0)),
        missing_adp=float(config.get("missingAdpDefault", 250)),
        gap_tier_threshold=int(config.get("gapTierThreshold", 4)),
    )

    source, projections, pooled, consensus, adp_rows, espn_rows, sleeper_rows, experts = (
        _load_inputs(
            config,
            inbox_dir=args.inbox_dir,
            force_inbox=args.inbox,
            from_data=args.from_data,
        )
    )
    espn_live = load_espn_adp(season=int(config.get("season", 2026)))
    players = merge_rankings(
        projections,
        pooled,
        consensus=consensus,
        adp_rows=adp_rows,
        espn_adp_rows=(*espn_rows, *espn_live),
        sleeper_adp_rows=sleeper_rows,
        config=merge_config,
    )
    if not players:
        print("generator produced no players", file=sys.stderr)
        return 1
    write_bundle(
        players,
        args.out_json,
        args.out_csv,
        seed_version=args.seed_version,
        experts=experts,
        source=source,
    )
    print(f"wrote {len(players)} players to {args.out_json} and {args.out_csv} ({source})")
    return 0


def _load_inputs(
    config: dict[str, Any],
    *,
    inbox_dir: Path,
    force_inbox: bool,
    from_data: bool,
) -> tuple[
    str,
    list[Any],
    dict[str, list[Any]],
    dict[str, list[Any]],
    list[AdpRow],
    list[AdpRow],
    list[AdpRow],
    dict[str, Any],
]:
    if from_data:
        from board import board_inputs

        projections, pooled, consensus, adp_rows = board_inputs()
        return (
            "bundled-data",
            projections,
            pooled,
            consensus,
            adp_rows,
            [],
            [],
            _experts_from_config(config),
        )
    key = None if force_inbox else api_key_from_env()
    if key:
        try:
            projections, pooled, consensus, adp_rows, experts = fetch_inputs(config, api_key=key)
            return (
                "fantasypros-api",
                projections,
                pooled,
                consensus,
                adp_rows,
                [],
                [],
                experts,
            )
        except FantasyProsError as exc:
            print(f"FantasyPros API failed ({exc}); trying inbox", file=sys.stderr)
    if _inbox_has_csv(inbox_dir):
        projections, pooled, consensus, adp_rows, espn_rows, sleeper_rows = read_inbox(inbox_dir)
        return (
            "inbox-csv",
            projections,
            pooled,
            consensus,
            adp_rows,
            espn_rows,
            sleeper_rows,
            _experts_from_config(config),
        )
    raise SystemExit(
        "No rankings source. Set FANTASYPROS_API_KEY, drop CSVs in tools/rankings/inbox/, "
        "or re-run with --from-data."
    )


def _experts_from_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "accuracyYear": config.get("accuracyYear"),
        "season": config.get("season"),
        "scoring": config.get("scoring"),
        "k": config.get("k"),
        "positions": config.get("positions", {}),
    }


def _inbox_has_csv(directory: Path) -> bool:
    return directory.is_dir() and any(directory.glob("*.csv"))


def generate_from_inbox(
    inbox_dir: Path,
    *,
    config_path: Path = DEFAULT_CONFIG,
) -> list[SeedPlayer]:
    config = load_config(config_path)
    projections, pooled, consensus, adp_rows, espn_rows, sleeper_rows = read_inbox(inbox_dir)
    return merge_rankings(
        projections,
        pooled,
        consensus=consensus,
        adp_rows=adp_rows,
        espn_adp_rows=espn_rows,
        sleeper_adp_rows=sleeper_rows,
        config=MergeConfig(
            k=float(config.get("k", 0.6)),
            nudge_clamp=float(config.get("nudgeClamp", 8.0)),
            missing_adp=float(config.get("missingAdpDefault", 250)),
            gap_tier_threshold=int(config.get("gapTierThreshold", 4)),
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
