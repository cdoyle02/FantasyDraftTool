# Weekly WR Skills Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four project Cursor skills for Thorman + Calandro weekly PPR WR boards and ESPN cross-refs.

**Architecture:** Clone personal `patrick-thorman-weekly-rb` / `thorman-rb-cross-ref` into `.cursor/skills/`, parameterized for WR + each expert id. Comet CDP/cookie auth; ESPN slot 4 for WR FA.

**Tech Stack:** Python 3 stdlib, Node CDP helper, FantasyPros partners API, ESPN fantasy API.

## Global Constraints

- Project path only: `FantasyDraftTool/.cursor/skills/<name>/`
- Explicit-run: `disable-model-invocation: true`
- Calandro names/descriptions include **2026 #1 WR accuracy**
- Never print cookies / Keychain secrets
- PPR weekly WR only

---

### Task 1: Rankings skills (Thorman + Calandro)

**Files:**
- `.cursor/skills/patrick-thorman-weekly-wr/SKILL.md`
- `.cursor/skills/patrick-thorman-weekly-wr/scripts/fetch_weekly_wr.py`
- `.cursor/skills/patrick-thorman-weekly-wr/scripts/cdp_fetch.mjs`
- `.cursor/skills/jamie-calandro-2026-wr1-weekly-wr/SKILL.md`
- `.cursor/skills/jamie-calandro-2026-wr1-weekly-wr/scripts/fetch_weekly_wr.py`
- `.cursor/skills/jamie-calandro-2026-wr1-weekly-wr/scripts/cdp_fetch.mjs`

- [ ] Resolve expert ids (Thorman 534 for WR; look up Calandro)
- [ ] Adapt fetch script for `position=WR`, expert constants
- [ ] Write SKILL.md with project script paths
- [ ] Smoke-test both scripts

### Task 2: Cross-ref skills

**Files:**
- `.cursor/skills/thorman-wr-cross-ref/SKILL.md` + `scripts/cross_ref_wr.py`
- `.cursor/skills/calandro-2026-wr1-cross-ref/SKILL.md` + `scripts/cross_ref_wr.py`

- [ ] Adapt RB cross-ref for WR slot/position 4; import sibling rankings script
- [ ] Write SKILL.md
- [ ] Smoke-test one cross-ref if ESPN env available
