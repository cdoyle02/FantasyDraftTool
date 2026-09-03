# Formula V5

Formula V5 is a selectable evolution of Formula V4 focused on late-round bench portfolio construction. V4 remains the default and is frozen; V5 adds bounded scoring terms without changing tier, survival, lookahead, or early starter logic.

## Activation

- Choose **Formula V4** or **Formula V5** in League setup or from the live **Active Formula** indicator.
- The selected version persists with the league. Switching versions clears stale recommendations and recalculates from the current board without resetting picks, keepers, or rankings.
- Historical evaluation records keep the formula version, parameters, and seed from when each pick was made.

## What V5 changes

### Negative VORP on bench assets

Late-phase bench candidates with negative VORP receive an explicit penalty scaled by how far below replacement they fall. Starter-fill candidates are damped so emergency roster completion is not over-penalized.

### Own-handcuff insurance

V5 classifies own handcuffs explicitly (same-team backup to a rank-1 starter with sufficient surplus). Raw handcuff value is scaled by league size (8-team ≈ 45%, 12-team ≈ 100%) and diminished for second/third/fourth rostered own handcuffs. External backfield RB2s are not penalized.

### Soft RB/WR bench balance

V5 removes V4's rigid late RB/WR balance push and replaces it with a soft neutral band based on usable depth (replacement-relative quality). Healthy depth inside the band receives no symmetry push.

### Reliability tiebreaker

On volatile late rosters, safer FLEX-eligible candidates can gain a small boost in close-score buckets (within 1.25 DVS points), capped at ±0.75. This cannot overturn a clearly superior pre-reliability pick.

## Diagnostic parameter

`v5_policy_strength` (0–1, default 1.0) blends V5 policy deltas. At `0.0`, V5 reproduces V4 ordering and shared breakdown values for isolation testing.

## A/B replay

Use `packages/dvs-engine/scripts/compare_formula_versions.py` to replay a schema-v2 evaluation export through V4 and V5 with the same board state. Output is written to a separate comparison document; source exports are never modified.

```bash
uv run python packages/dvs-engine/scripts/compare_formula_versions.py path/to/export.json --json-out comparison.json
```

## V5 breakdown fields

V5 adds optional breakdown fields such as `negative_vorp_adjustment`, `adjusted_handcuff_bonus`, `bench_balance_adjustment`, `reliability_adjustment`, and `v5_policy_strength`. These appear only when Formula V5 is active.
