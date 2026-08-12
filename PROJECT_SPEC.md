# Fantasy Football Draft Assistant — Project Spec

## 1. Elevator Pitch

A platform-agnostic live draft assistant (works alongside ESPN, Sleeper, or Yahoo — not dependent on any one of them) that recommends who to draft in real time, using a proprietary value formula that blends VORP-style positional scarcity, tier-cliff urgency, roster construction needs, and opponent draft-need prediction. Secondary goal: support mock drafts, which also double as the simulation harness used to tune the formula.

Full PPR scoring. Draft picks enter the tool either via manual fast-entry (any platform) or auto-sync (Sleeper first, since it has the most permissive API) — both feed the same internal draft state.

---

## 2. Core Principles

- **Platform-agnostic first.** Manual entry must work everywhere and must be fast enough to use under a pick clock (~90 sec). Sync is a nice-to-have layered on top, not a dependency.
- **The formula is the product.** Everything else (UI, sync, import) is scaffolding around the Draft Value Score (DVS) engine. Keep the engine as a pure, isolated module — no UI or fetch logic inside it — so it can be unit tested and later reused inside the mock draft simulator.
- **Data vs. opinion are separate layers.** Imported projections/ADP are the baseline. User adjustments (boosts, fades, custom tiers, "my guys", "never draft") sit on top and persist independently of re-imports.
- **Explainable recommendations.** Every recommendation shows *why* (VORP, tier cliff, survival probability, need) — not just a ranked list. Trust is built by showing the reasoning.
- **The simulator is also the test harness.** Phase 3's mock draft engine exists to let us run hundreds of simulated drafts and empirically tune formula weights, not just to give the user practice drafts.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Interface Layer                     │
│   Draft board · My roster vs league rosters · Rec panel  │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│                 Draft State Manager                       │
│  Unified state regardless of input source:                │
│   - Manual entry (type-ahead search, ~2 sec per pick)     │
│   - Sleeper API polling sync                               │
│   - Mock draft simulator (Phase 3)                         │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│              Formula Engine (DVS — pure module)            │
│  Input: player pool + draft state + all rosters + settings │
│  Output: ranked recs w/ tier labels + explanations         │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│                      Data Layer                            │
│   Imported projections/ADP (e.g. FantasyPros CSV export)   │
│   + User adjustment layer (persisted, independent of import│
└─────────────────────────────────────────────────────────┘
```

---

## 4. The Formula: Draft Value Score (DVS)

Recomputed for every available player after each pick. Six components combine into a single score, plus a tier label.

### 4.1 Baseline Value — VORP
`VORP = ProjectedPoints(player) - ReplacementLevel(position)`

Replacement level is derived from league settings (team count, starting slots, flex eligibility), e.g. in a 12-team 1-QB league: roughly QB13, TE13, RB~30, WR~36 replacement baseline (exact index math based on starters + flex slots). This is what naturally suppresses early QB/TE picks — no hardcoded "don't draft QB early" rule needed, though we add guardrails as a belt-and-suspenders layer (4.6).

### 4.2 Tier Cliff Urgency
Players are grouped into tiers per position (from imported rankings + user adjustments). Score boosted based on:
- Point drop-off from this player's tier to the next tier down
- Probability that the remaining players in this tier are gone before the user's next pick (derived from 4.3)

### 4.3 Survival Probability
`P(available at next pick)` estimated from ADP distribution + number of picks until the user is back on the clock. Feeds the "CAN'T PASS" alarm: high VORP + low survival = urgent flag.

### 4.4 Roster Need Multiplier
Diminishing-returns curve per position based on slots already filled on the user's roster. Nearly flat in early rounds (best-player-available dominates), sharpens as bench/starter slots fill. Flex eligibility keeps RB/WR need from ever hitting zero.

### 4.5 Opponent Demand Model
For each other roster in the league, generate a probability distribution over their likely next position picks based on their unfilled slots. This feeds directly into 4.3 (survival probability) and 4.2 (tier urgency) — e.g., if the teams picking between the user's turns all still need a QB, the model should anticipate a QB run before it happens.

### 4.6 Vet Guardrails
Adjustable (not hardcoded) weights encoding conventional wisdom:
- Suppress QB/TE value until a threshold VORP is crossed (1-QB leagues)
- Hard-suppress K/DST until final 2 rounds
- Target RB/WR balance bands by round range

These are weights, not hard blocks — an extreme value can still override them.

### 4.7 Output
Not just a sorted list — three tiers of advice per recommended player:
- **CAN'T PASS** — high value + high scarcity/urgency alarm
- **BEST PICK** — top of the ranked list under normal conditions
- **SAFE TO WAIT** — good player, but survival probability says he'll likely be there next round; take the scarcer position now instead

---

## 5. Data Model (draft skeleton)

```
Player {
  id, name, position, team,
  projectedPoints, adp,
  tier (imported + user override),
  userAdjustment: { boost/fade delta, note, "myGuy" | "avoid" | null }
}

LeagueSettings {
  teamCount, rosterSlots: { QB, RB, WR, TE, FLEX, superflex?, bench, K, DST },
  scoringFormat: "PPR" | "halfPPR" | "standard",
  snakeOrAuction, keeperOrRedraft
}

DraftState {
  pickHistory: [{ pickNumber, teamId, playerId, timestamp }],
  currentPick, teamOnClock,
  rosters: { [teamId]: Player[] }
}

RecommendationResult {
  playerId, dvsScore, tierLabel ("CAN'T PASS"|"BEST PICK"|"SAFE TO WAIT"),
  breakdown: { vorp, tierUrgency, survivalProb, needMultiplier, opponentDemandFactor, guardrailAdjustment }
}
```

---

## 6. Build Phases

### Phase 1 — Draftable MVP (build first)
- CSV import of projections/ADP + user adjustment layer (UI to boost/fade/tier/tag players)
- DVS engine v1: VORP + tier cliffs + roster need + guardrails (skip opponent demand model for v1 — add in Phase 1.5 once core works)
- Manual pick entry: fast type-ahead search, works for any platform/live draft
- Recommendation panel with explainable breakdown
- **Goal: usable in a real live draft on any platform before anything else is built.**

### Phase 1.5 — Opponent Demand Model
- Add full opponent roster tracking + demand distribution
- Wire into survival probability and tier urgency

### Phase 2 — Sleeper Sync
- Poll Sleeper draft API, auto-log picks into the same DraftState used by manual entry
- Manual entry remains the fallback/override at all times

### Phase 3 — Mock Draft Simulator
- Simulate opponent picks from ADP + demand model
- Doubles as the formula test harness: run N simulated drafts, score resulting rosters, use results to empirically tune formula weights

### Phase 4 — Tuning & Extras
- Weight tuning from simulation results and real draft outcomes
- Opponent tendency learning (if a league is drafted repeatedly)
- Injury news import
- Keeper league support

---

## 7. Tech Stack (proposed — adjust in Cursor as needed)

- **Frontend:** React + TypeScript, Tailwind for styling
- **Formula engine:** Plain TypeScript module, framework-agnostic, unit-testable in isolation (critical — this is the core IP)
- **State:** Local state/store (Zustand or similar) for draft state; no backend required for MVP if data import is file-based and everything runs client-side
- **Data import:** CSV parser (e.g. PapaParse) for FantasyPros-style exports
- **Sync (Phase 2):** Sleeper public draft API (polling, no auth required for public leagues)
- **Persistence:** localStorage or IndexedDB for user adjustment layer + league settings (client-side is fine until multi-device sync is needed)

---

## 8. Open Questions / TODO Before Coding Starts

- [ ] League size (e.g. 12-team)
- [ ] Roster slots: # of RB/WR/TE/FLEX, superflex or not, bench size, K/DST or not
- [ ] Snake or auction draft
- [ ] Redraft or keeper league
- [ ] If multiple leagues: which one is the "money league" the default formula weights should be tuned to

**Note:** Ship Phase 1 with sensible 12-team, 1-QB, standard-flex defaults and make all settings configurable — don't block starting the build on these answers.

---

## 9. Suggested Repo Structure

```
/src
  /engine        <- DVS formula, pure TS, fully unit tested
    dvs.ts
    vorp.ts
    tiers.ts
    survivalProbability.ts
    opponentDemand.ts
    guardrails.ts
  /data
    importers/   <- CSV parsing, projection/ADP normalization
    adjustments/ <- user boost/fade/tier override layer
  /draftState
    manualEntry.ts
    sleeperSync.ts
    draftStateStore.ts
  /simulator       <- Phase 3, reuses /engine directly
  /components      <- React UI (draft board, roster panels, rec panel)
  /types           <- shared Player / LeagueSettings / DraftState types
```
