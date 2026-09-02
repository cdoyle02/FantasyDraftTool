export const FOOTBALLERS_CSV_GENERATION_PROMPT = `Using the attached Fantasy Footballers cheat-sheet PDF, generate a single DVS-ready CSV with one row per ranked player or defense.

Use exactly these columns, in this order:

season, as_of_date, ranking_type, scoring_profile, league_size, position, position_rank, tier_number, tier_rank, tier_size, tier_value_multiplier, player_id, player_name, player_slug, team, bye_week, age, experience, adp_round_pick, adp_overall, risk_score, upside_score, tags, is_my_guy, is_value, is_bust, is_sleeper, is_rookie, is_injury_concern, is_breakout, source_page, source_cheatsheet_id, source_url

Requirements:

- Extract the league name, date, rankings, tier boundaries, ADP, risk, upside, teams, and visible player-tag icons from the PDF.
- Preserve \`adp_round_pick\` as displayed text. Calculate \`adp_overall\` as \`(round - 1) × league_size + pick\`.
- Calculate \`tier_rank\` within each tier and \`tier_size\` as the number of players in that tier.
- Use these tier multipliers:
  - QB: 1, 0.95, 0.87, 0.85, 0.82, 0.795, 0.725, 0.66, 0.50
  - RB: 1, 0.94, 0.85, 0.76, 0.68, 0.63, 0.57, 0.50, 0.38, 0.28
  - WR: 1, 0.95, 0.80, 0.72, 0.70, 0.66, 0.62, 0.60, 0.52, 0.45, 0.32
  - TE: 1, 0.90, 0.78, 0.70, 0.58, 0.54, 0.45, 0.29
- Store tags as pipe-delimited values using: \`my_guy\`, \`value\`, \`bust\`, \`sleeper\`, \`rookie\`, \`injured\`, and \`breakout\`. Populate the corresponding one-hot columns with 1 or 0.
- D/ST and kickers do not use tiers. Include their straight rankings and leave tier, ADP, risk, and upside fields blank.
- If the league does not use a position, do not invent rows for it.
- Use official player metadata already available in the project for IDs, slugs, bye weeks, ages, and experience. Leave unavailable fields blank rather than guessing.
- Validate continuous position ranks, tier membership, row counts against the PDF, unique position/rank combinations, and zero formula-like or malformed values.
- Output only the completed CSV.`
