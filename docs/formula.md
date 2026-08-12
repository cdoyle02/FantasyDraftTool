# Draft Value Score assumptions

The first engine version ranks each available player from four explainable
components. All weights and thresholds belong to league configuration rather
than UI code.

## Baseline value

Value over replacement is projected full-PPR points minus the projected points
of the replacement player at that position. Replacement indices derive from
team count, starting slots, and flex demand. Missing projections are invalid
input, not zero-value players.

## Tier urgency

A player's tier receives urgency from the projected-point drop to the next
position tier and the number of same-tier players remaining. Explicit user tier
overrides take precedence over imported tiers.

## Roster need

Need is deliberately shallow early in a draft and increases as starting slots
become scarce. RB and WR continue to receive flex credit after their named
starting slots fill. Bench space must not make a filled starting position more
valuable than an open one.

## Guardrails

The MVP applies configurable soft penalties to early QB/TE selections in 1-QB
leagues and to K/DST selections before the final rounds. They are adjustments,
not exclusions, so exceptional value can still rank first.

## Labels

- **CAN'T PASS** identifies exceptional value with a major tier cliff.
- **BEST PICK** identifies the normal highest-ranked recommendations.
- **SAFE TO WAIT** identifies useful players without immediate scarcity.

Every result includes the raw component values and a short explanation. Scores
are comparative within the current draft state and should not be interpreted as
projected fantasy points.

Opponent demand and ADP-based survival probability are intentionally deferred to
Phase 1.5. Until then, labels must not claim that opponent picks were predicted.
