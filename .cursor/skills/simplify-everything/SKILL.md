---
name: simplify-everything
description: >-
  Switches to Ask mode, rewrites jargon-heavy plans and summaries into plain
  English from what_is_unclear, then switches back to Agent mode when done. Use
  when the user says something is unclear, doesn't make sense, or asks to
  simplify; when they paste confusing sentences; or when they would otherwise
  manually toggle Ask mode just for an explanation.
---

# Simplify Everything

Run a **mode round-trip**: Ask → plain-language explanation → Agent. The user should not manually switch modes for this.

## User input

| Parameter | Required | What to use |
|-----------|----------|-------------|
| **what_is_unclear** | Yes | Exact sentences, bullet labels, section titles, or `@`-referenced excerpt the user names as confusing |
| **source_context** | No | Prior summary, full plan, doc path, or "everything you just said" when the snippet needs surrounding context |

If the user only says "simplify that" or "these two sentences mean nothing to me", use the **most recent agent output** or **most recently referenced file** as `what_is_unclear`.

## Mode workflow (required)

Follow these phases in order every time this skill runs.

### Phase 1 — Enter Ask mode

1. Call `SwitchMode` with:
   - `target_mode_id`: `"ask"`
   - `explanation`: one sentence, e.g. "Switching to Ask mode to explain unclear text — read-only, no edits."

2. If Ask mode is unavailable or the switch is rejected:
   - Say in one line that you are continuing under Ask-mode rules (read-only).
   - Do **not** edit files, run shell commands, or use write tools for the rest of this skill.

3. While in Ask mode, **read-only tools only** (`Read`, `Grep`, `Glob`, etc.). No implementation.

### Phase 2 — Simplify

1. **Lock scope** — One line restating what you are simplifying.
2. **De-jargon** — One numbered section per confusing item (see output template).
3. **Sanity check** — Could someone who doesn't write code follow this?

Do not start or continue implementation work in this phase.

### Phase 3 — Return to Agent mode

1. After the explanation is complete, call `SwitchMode` with:
   - `target_mode_id`: `"agent"`
   - `explanation`: one sentence, e.g. "Plain-language explanation complete — resuming Agent mode for implementation work."

2. If the switch is unavailable or rejected, tell the user to switch back to Agent mode manually, then stop.

3. End with the closing line below. Do not start coding unless the user's next message asks for it.

**Never skip Phase 3.** The round-trip back to Agent is the point of this skill.

## Output template

```markdown
**N. [Plain title — no internal codenames]**

[Optional: "Right now…" or "Today…" — what's confusing or risky]

[What this actually means — concrete user-visible outcome]

[Optional: why it matters if we skip or get it wrong]
```

### Rules

- **No unexplained jargon** — Prefer "show an error instead of faking it" over "fail closed".
- **Outcomes over architecture** — User experience first; file names only if requested.
- **Keep their scope** — Simplify only `what_is_unclear` unless they asked for more.
- **Match their depth** — Two confusing sentences → two short sections.
- **Bold sparingly** — Only for the one behavior that must not be missed.

## When to invoke

| User signal | Action |
|-------------|--------|
| "What does X mean?", "simplify", "plain English", "mean nothing to me" | Run full Ask → simplify → Agent workflow |
| Same message also says "and then implement" | Still simplify first; return to Agent; wait for confirmation before coding |
| They wanted a shorter technical summary | Tighter expert summary instead — not this skill |

## Example

**what_is_unclear:**  
"Green CI + fail-closed scoring — fix lint/type/CI, never silently use the dev scorer in prod."  
"Replay ingestion — normalized pick-source contract + replay fixtures."

**Good output (delivered in Ask mode, then switch back to Agent):**

**1. Make the live app honest about scoring**

Right now, automated checks are failing, and if the real ranking engine isn't available, the app can quietly switch to a fake "dev" scorer. That could give you bad rankings on draft day without you noticing.

This batch: get those checks passing again, and if the real engine can't run, **stop and show an error** instead of faking scores. You can still enter picks by hand.

**2. Let you load a practice draft from a file**

Before play/pause/reset controls, the app needs a way to take a list of already-made picks (a recorded mock draft) and feed them the same way a live draft would.

That's replay ingestion: dump in the pick list, convert it to the app's internal format, and apply those picks.

Ready to continue the original work when you are.

## Closing line

Always end Phase 3 with one short line, e.g. "Ready to continue the original work when you are." Do not append implementation plans unless asked.
