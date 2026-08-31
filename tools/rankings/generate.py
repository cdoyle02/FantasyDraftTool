"""Generate the committed expert-pooled rankings seed.

Usage:
  uv run python tools/rankings/generate.py
  uv run python tools/rankings/generate.py --inbox
  uv run python tools/rankings/generate.py --from-data

Default: Fantasy Footballers workbook + cheatsheet for QB/RB/WR/TE, bundled or FantasyPros K/DST.
API key (never shipped in the app): FANTASYPROS_API_KEY (K/DST refresh only).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cheatsheet import DEFAULT_CHEATSHEET, cheatsheet_inputs, overlay_cheatsheet_tiers
from espn_adp import load_espn_adp
from fetch import FantasyProsError, api_key_from_env, fetch_k_dst_inputs
from footballers import DEFAULT_WORKBOOK, footballers_inputs
from merge import AdpRow, MergeConfig, SeedPlayer, merge_rankings
from store import load_config, read_inbox, write_bundle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_JSON = REPO / "apps" / "web" / "src" / "data" / "expertRankings.json"
DEFAULT_CSV = HERE / "out" / "expert-rankings.csv"
DEFAULT_CONFIG = HERE / "experts.json"
DEFAULT_INBOX = HERE / "inbox"
SEED_VERSION = "2026.6"


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
        help="Use Footballers workbook + cheatsheet + bundled K/DST (no live FantasyPros fetch)",
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
    if force_inbox and _inbox_has_csv(inbox_dir):
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

    if from_data or not force_inbox:
        return _load_footballers_hybrid(config, from_data=from_data)

    raise SystemExit(
        "No rankings source. Drop CSVs in tools/rankings/inbox/ and use --inbox, "
        "or re-run without --inbox to use the Footballers workbook."
    )


def _load_footballers_hybrid(
    config: dict[str, Any],
    *,
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
    workbook = _workbook_path(config)
    gap = int(config.get("gapTierThreshold", 4))
    skill_projections, skill_pooled, skill_consensus = footballers_inputs(
        workbook,
        gap_tier_threshold=gap,
    )
    cheat_ranked, cheat_adp = cheatsheet_inputs(_cheatsheet_path(config))
    skill_pooled = overlay_cheatsheet_tiers(skill_pooled, cheat_ranked)
    skill_consensus = overlay_cheatsheet_tiers(skill_consensus, cheat_ranked)

    k_dst_source = "bundled-k-dst"
    k_projections: list[Any] = []
    k_pooled: dict[str, list[Any]] = {}
    k_consensus: dict[str, list[Any]] = {}
    adp_rows: list[AdpRow] = []

    key = None if from_data else api_key_from_env()
    if key:
        try:
            k_projections, k_pooled, k_consensus, adp_rows = fetch_k_dst_inputs(config, api_key=key)
            k_dst_source = "fantasypros-k-dst"
        except FantasyProsError as exc:
            print(f"FantasyPros K/DST fetch failed ({exc}); using bundled K/DST", file=sys.stderr)

    if not k_projections:
        from board import k_dst_board_inputs

        k_projections, k_pooled, k_consensus, adp_rows = k_dst_board_inputs()

    projections = [*skill_projections, *k_projections]
    pooled = {**skill_pooled, **k_pooled}
    consensus = {**skill_consensus, **k_consensus}
    source = f"footballers+cheatsheet+{k_dst_source}"
    return (
        source,
        projections,
        pooled,
        consensus,
        [*cheat_adp, *adp_rows],
        [],
        [],
        _experts_from_config(config),
    )


def _workbook_path(config: dict[str, Any]) -> Path:
    configured = config.get("footballersWorkbook")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = HERE / path
        return path
    return DEFAULT_WORKBOOK


def _cheatsheet_path(config: dict[str, Any]) -> Path:
    configured = config.get("footballersCheatsheet")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = HERE / path
        return path
    return DEFAULT_CHEATSHEET


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
