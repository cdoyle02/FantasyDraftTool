# DVS Formula V4 — Draft Decision Engine

V4 upgrades the recommendation engine from isolated player scoring to a **one-turn lookahead decision model**. Versions 1–3 remain available via `formula_version`.

## Decision equation

```text
V4(p) = m(p)
      + w_wait  * wait_loss(p)
      + w_tier  * tier_opportunity(p)
      + w_look  * next_pick_value(p)
      + shape_adjustment(p)
      + guardrails(p) + tags(p)
```

Reported for explainability: `two_pick_path_value(p) = m(p) + next_pick_value(p)`.

## Term responsibilities

| Term | Responsibility | Scale |
|------|----------------|-------|
| `m(p)` | Immediate roster marginal value (starters, FLEX/SF, bench discount, caps) | Full points |
| `wait_loss(p)` | Same-position replaceability weighted by survival risk | × 0.35 |
| `tier_opportunity(p)` | Fantasy Footballers tier cliff × tier exhaustion | × 0.30, capped ~7.5 pts |
| `next_pick_value(p)` | Expected best cross-position value after drafting `p` | × 0.85 |
| `shape_adjustment(p)` | Roster construction nudge (additive, not multiplicative) | ±18 pts max |
| `guardrails(p)` | Conventional vetoes (early QB/TE, K/DST, caps) | Additive |

Survival, opponent demand, and positional runs **never add score directly** — they only adjust probabilities.

## Wait-loss correction (V3 → V4)

**V3 (wrong):** wait-loss omitted survival weighting, treating `(1 - S)` as 1.

**V4 (correct):**

```text
wait_loss = (1 - S) * max(0, m - F)
```

Example: `m = 80`, `F = 50`

| Survival | V4 wait-loss | V3-style (S=0) |
|----------|--------------|----------------|
| 90% | 3.0 | 30.0 |
| 50% | 15.0 | 30.0 |
| 10% | 27.0 | 30.0 |

## Intervening opponent picks vs pick distance

`picks_until_team_turn` measures distance to the user's **next pick slot** (including that slot). Survival and disappearance use **intervening opponent picks** — the ordered opponent selections strictly before that slot.

| Situation | Pick distance | Intervening opponent picks |
|-----------|---------------|----------------------------|
| Back-to-back (user on clock, next pick is yours) | 1 | 0 → all available players have survival 1.0 |
| Pick 1, 12-team snake | 23 | 22 (picks 2–23) |

When intervening count is 0, wait-loss is 0, tier exhaustion is 0, and fallback/lookahead use the current board exactly.

## One-turn simulation

Between your turns, V4 runs a seeded Monte Carlo simulation (`one_turn_sims`, default 48) of opponent picks:

1. Walk the intervening schedule in pick order.
2. For each opponent pick, sample from a truncated ADP pool weighted by `per_pick_hazard × roster_shape_need(updated roster) × run_pressure`.
3. Update that team's simulated roster before their next pick.

From simulated paths, V4 derives:

- **Survival** — fraction of paths where the player remains
- **Fallback** — mean best same-position marginal among survivors (excluding the evaluated player)
- **Tier exhaustion** — fraction of paths where the tier is empty; hard 0 when `players_in_tier > intervening_picks`
- **Next-pick value** — mean max cross-position marginal among survivors after simulating `roster + {p}`

This replaces the prior independent-survival chain for wait-loss, tier exhaustion, and lookahead.

## Tier integration

```text
cliff_shrunk = cliff * scale / (cliff + scale)
P_exhaust    = fraction of sim paths where tier is empty
tier_opportunity = cliff_shrunk * P_exhaust
```

Hard rule: if more players remain in a tier than intervening opponent picks, `P_exhaust = 0`.

Tiers affect decisions through `tier_opportunity`, not a raw projection bonus. Same-tier players share cliff and exhaustion, avoiding artificial separation.

## Lookahead

For each candidate `p`:

1. Simulate `roster + {p}`
2. Recompute marginals for a pruned next-turn pool (top 6 per position)
3. `next_pick_value(p) = mean over sim paths of max surviving marginal`

Non-candidates share a baseline next-pick expectation for performance.

## Opponent demand and positional runs

For each intervening pick, `roster_shape_need` on the **updated** opponent roster adjusts pick weight. Positional run pressure compares recent pick frequency to a **weighted** FLEX/SUPERFLEX baseline (same weights as replacement-level allocation).

## Default parameters

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `lookahead_weight` | 0.85 | Future opportunity matters but should not dominate immediate value |
| `wait_loss_weight_v4` | 0.35 | Overlap with lookahead; keeps wait-loss as tie-breaker |
| `tier_weight` | 0.30 | Expert signal without double-counting projections |
| `tier_cliff_scale` | 25.0 | Saturates large cliffs so tiers nudge rather than dominate |
| `need_points_scale` | 12.0 | Additive roster construction, self-scaling with draft phase |
| `need_points_cap` | 18.0 | Prevents construction from vetoing elite value |
| `opponent_demand_weight_v4` | 0.6 | Conservative opponent modeling |
| `one_turn_sims` | 48 | Seeded paths; fast enough for live drafting |
| `sim_pick_pool` | 40 | Truncated opponent choice set per pick |

## Remaining limitations

- Replacement levels use the full pre-draft pool, not remaining available players
- One-turn horizon only (no multi-pick tree search)
- Opponent picks are need-weighted ADP sampling, not a full opponent engine
- Lookahead reuses sim paths with `p` excluded; does not re-simulate opponent reactions to your pick
- Finite seeded MC introduces small sampling noise
- Lookahead pool is pruned per position (small constant bias)

## Activation

- Python default: `FormulaParams(formula_version=4)`
- API / browser: `settings.formulaVersion: 4` (web app default)
- Prior versions: set `formula_version` to 1, 2, or 3 explicitly

## V4.1 — Late-round roster optimization

V4.1 adds an optional late-round layer on top of the V4 core. Every new term is **zero** when metadata is absent or the draft is early, so Footballers projections/tiers/ADP remain the primary ranking inputs.

### Decision equation (V4.1)

```text
decision_score = V4(p) + optionality_value(p)
optionality_value = max(late_round_upside, handcuff_bonus, ir_stash_value)   # default combine
```

Special teams (K/DST) are handled separately:

- **Hard gate (default):** ineligible K/DST are removed from scoring and candidate selection until their timing window.
- **Position caps:** second K/DST at cap contributes **0 marginal** (lineup caps on direct slots and bench).
- **Scarcity zeroing:** K/DST tier cost and wait-loss scale to 0; run pressure fixed at 1.0.
- **Candidate-conditioned lookahead:** future K/DST eligibility is evaluated against `roster + drafted_candidate` at the next round.

### Metadata inputs (optional)

| Field | Source | Used for |
|-------|--------|----------|
| `upside_score`, `is_rookie`, `is_breakout` | Footballers cheatsheet | Late-round upside tie-breaking |
| `risk_score` | Cheatsheet | Bounded handcuff modifier only (±15% on role probability) |
| `depth_chart_rank`, `depth_chart_source` | Derived from team+position ADP order | Handcuff pairing; `"derived"` gets 0.7 confidence |
| `ir_eligible`, `injury_status` | Manual / explicit only | IR stash (not `is_injury_concern` alone) |
| `keeper_slots`, `reserved_rosters` | League settings + draft state | Live round count and pre-draft rosters |

Missing metadata degrades gracefully: optionality terms stay at 0.

### Keeper replacement

`demand_adjusted_replacement` ships **disabled** (`False`). Static replacement levels match pre-V4.1 behavior. Keeper round accounting: `rounds = roster_size - keeper_slots`.

### Monte Carlo convergence (measured)

Reference: 480 paths. Tested at team 6 (middle seat) on three boards with 4 seeds each.

| Board | sims=48 | Top-1 | Top-3 | max Δ survival | max Δ next-pick | Runtime |
|-------|---------|-------|-------|----------------|-----------------|---------|
| Pick 1 empty | 48 | OK | OK | ≤ 0.05 | ≤ 0.02 | ~180 ms |
| Mid partial roster | 48 | OK | OK | 0.00 | ≤ 0.04 | ~310 ms |
| Penultimate K/DST open | 48 | OK | OK | 0.00 | 0.00 | ~430 ms |

**Recommendation:** keep `one_turn_sims = 48`. All boards pass top-1, top-3, and tolerance checks (Δ survival ≤ 0.15, Δ next-pick ≤ 1.0, Δ score ≤ 1.0) without raising the default.

### V4.1 limitations

- IR eligibility is not inferred from cheatsheet injury flags; use explicit fields or the `irStash` tag.
- Handcuff depth charts are ADP-derived heuristics, not NFL official charts.
- `demand_adjusted_replacement` remains off until backtesting justifies enabling it.
- Regenerate `expertRankings.json` after rankings pipeline changes to pick up cheatsheet metadata in the web seed.
