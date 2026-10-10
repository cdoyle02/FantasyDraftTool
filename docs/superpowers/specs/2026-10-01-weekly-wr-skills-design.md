# Weekly WR Expert Ranking Skills (Thorman + Calandro)

**Date:** 2026-10-01  
**Status:** Approved — implemented in `.cursor/skills/`  
**Scope:** Project Cursor skills only (no in-app UI / API in this pass)

## Goal

Ship four **project** Agent Skills under `FantasyDraftTool/.cursor/skills/` that mirror the existing Patrick Thorman weekly RB + cross-ref pattern, for **PPR wide receivers**, for:

1. **Patrick Thorman** (Establish the Run)
2. **Jamie Calandro** (RotoBaller) — call out **2026 in-season WR accuracy #1** in skill names and descriptions

Each expert gets a full weekly board skill and a separate ESPN team roster / FA-waiver cross-ref skill.

## Decisions

| Topic | Choice |
|-------|--------|
| Location | Project skills: `.cursor/skills/<name>/` (accessible in this repo) |
| Personal copies | Not required for this pass |
| Scoring | Weekly **PPR**, position **WR** |
| Auth | Same as Thorman RB: Comet CDP `127.0.0.1:9333`, then Comet FantasyPros cookies |
| Data source | FantasyPros partners consensus API with expert `filters=<id>` (not ECR) |
| UI / API | Out of scope — skills only |
| Explicit-run | `disable-model-invocation: true` on all four |
| Catalog | Optional: note in personal `CATALOG.md` that project owns these; no duplicate install under `~/.cursor/skills` |

## Skills

| Folder / name | Slash | Purpose |
|---------------|-------|---------|
| `patrick-thorman-weekly-wr` | `/patrick-thorman-weekly-wr` | Full Thorman weekly PPR WR board |
| `thorman-wr-cross-ref` | `/thorman-wr-cross-ref` | Thorman WR ranks × one ESPN team’s WRs + FA/waivers |
| `jamie-calandro-2026-wr1-weekly-wr` | `/jamie-calandro-2026-wr1-weekly-wr` | Full Calandro weekly PPR WR board (**2026 #1 WR accuracy**) |
| `calandro-2026-wr1-cross-ref` | `/calandro-2026-wr1-cross-ref` | Calandro WR ranks × one ESPN team’s WRs + FA/waivers |

### Description requirements

- Third person; WHAT + WHEN; explicit-run / slash triggers.
- Name expert, site, PPR WR, weekly.
- Calandro skills must state **2026 in-season WR accuracy #1** (or equivalent “2026 #1 WR”) in the YAML `description` and SKILL title body.

## Architecture

Clone the personal Thorman RB skill stack into the project, parameterized for WR + expert:

### Rankings scripts

- `scripts/fetch_weekly_wr.py` per expert skill (or shared helper copied once and specialized).
- API shape (same host as RB):

  `https://partners.fantasypros.com/api/v1/consensus-rankings.php?sport=NFL&position=WR&type=weekly&scoring=PPR&filters=<EXPERT_ID>`

- Reject payload unless `filters` matches the expert id and `total_experts` is `1`.
- Resolve **Calandro** and confirm **Thorman** expert ids during implementation (Thorman RB uses **534**; verify WR filter uses the same id).
- Copy / adapt `cdp_fetch.mjs` from the Thorman RB skill.
- Default week = FantasyPros current week; `--week N` when named.
- Stdout: markdown table `Rank | Player | Team | Opp | Proj` + one footer line (week, PPR, expert/site, count, last-updated, source, URL).
- Never print cookies / Keychain / CDP headers.

### Cross-ref scripts

- `scripts/cross_ref_wr.py` per cross-ref skill.
- Join:
  1. Expert weekly PPR WR board (import sibling rankings script)
  2. ESPN team rostered WRs (starters + bench)
  3. League FREEAGENT / WAIVERS WRs ranked by that expert
- ESPN WR lineup slot id **4**; include FLEX / WR/TE / RB/WR slots where a WR is rostered (same spirit as RB cross-ref’s started-slot set).
- Inputs: `--league-id`, `--team` / `--owner`, optional `--week`, `--season`, `--env-file`.
- Ask before reading `.env` when user rules require it.
- Output: header line; roster table; waiver table of available WRs ranked **ahead of** the team’s current WRs; footer. Never invent ranks.

### SKILL.md path references

Use **project-relative** absolute paths in instructions, e.g.:

```bash
python3 /Users/michaeldoyle/repos/FantasyDraftTool/.cursor/skills/patrick-thorman-weekly-wr/scripts/fetch_weekly_wr.py
```

Prefer documenting `$REPO/.cursor/skills/...` so clones work; scripts resolve siblings via `Path(__file__)`.

## Errors

- FantasyPros auth fail → tell user to open Comet, stay signed into FantasyPros, retry; do not invent ranks.
- Missing league / team → ask; do not guess.
- ESPN fail → report clearly; still show rankings table when rankings-only skill ran.
- Wrong expert filter in API response → hard fail.

## Testing

- Smoke-run each rankings script for current week (requires Comet session).
- Smoke-run one cross-ref with a known league/team when credentials available.
- Confirm Calandro payload is single-expert and names match.

## Out of scope

- Week WR UI tab / `apps/api` endpoints
- QB / TE skills
- Dual install under `~/.cursor/skills` or `~/.claude/skills`
