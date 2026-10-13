# Claude Code — FantasyDraftTool

Shared agent instructions live in the portable SSOT:

@AGENTS.md

## Claude-only notes

- Prefer project skills under `.cursor/skills/` when present locally (often gitignored — recreate on new machines).
- For ESPN/week tools in chat, prefer the ESPN MCP / `draft_api` paths documented in `AGENTS.md` over pasting cookies into prompts.
- Deep context: `docs/audits/2026-10-10-full-codebase-analysis.md`.
- Personal overrides: use gitignored `CLAUDE.local.md` if needed; set Project instructions to also load `AGENTS.md` if a local CLAUDE file would otherwise shadow it.
