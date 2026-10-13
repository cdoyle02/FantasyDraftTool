# Agent instructions — FantasyDraftTool

README for humans: [README.md](README.md). This file is for coding agents.

## Stack

- Node ≥18 (README prefers 20+) + **pnpm 9** (`packageManager` in root `package.json`)
- Python **≥3.13** + **uv** (workspace: `apps/api`, `packages/dvs-engine`)
- Monorepo: `apps/web` (Vite React PWA), `apps/api` (FastAPI), `packages/dvs-engine` (pure DVS), `tools/espn-mcp`, `tools/rankings`

## Commands (verified patterns)

```bash
pnpm install
uv sync --all-packages --all-groups   # or --all-extras as in CI
pnpm api:dev                          # http://localhost:8000
pnpm dev                              # http://localhost:5173
pnpm test                             # web vitest
pnpm test:python                      # pytest (engine, api, rankings)
pnpm build                            # engine wheel + web
```

CI: `.github/workflows/ci.yml` (python + web + e2e). **espn-mcp tests are not in CI** — run from `tools/espn-mcp` when changing MCP.

## Repository map

| Path | Purpose |
|------|---------|
| `apps/web` | Draft UI, Dexie persistence, Pyodide offline DVS, Week D/ST + K |
| `apps/api` | Stateless recommendations + week odds / Kyle / Jared / ESPN leagues |
| `packages/dvs-engine` | Pure scoring; no network/DB |
| `tools/espn-mcp` | ESPN MCP stdio + hosted HTTP (separate Railway) |
| `tools/rankings` | Offline rankings → web seed JSON |
| `data/rosters` | Committed ESPN roster snapshots |
| `docs/audits/` | Full land-of-the-land + chat wishlist (2026-10-10) |

## Working rules

- Prefer existing patterns; do not invent new package layouts.
- Draft state is **browser-local** (Dexie). Do not assume a server draft store.
- Week boards and MCP weekly tools share `draft_api`; MCP bridge tools need `draft_api` installed (Docker does; bare `tools/espn-mcp` may not).
- Search for an existing pattern before adding abstractions.
- Keep changes scoped to the requested task; preserve unrelated working-tree changes.

## Safety

- Never read, print, commit, or paste `.env`, ESPN cookies, MCP tokens, or Odds keys.
- Ask before destructive git (`reset --hard`, `clean -fdx`) — protects local `.firecrawl/` and untracked work.
- Treat scrapers (FantasyPros, Ballers) and undocumented ESPN APIs as fragile.

## Definition of done

- Relevant tests for touched package pass (`pnpm test` / `pnpm test:python` / espn-mcp pytest when MCP changes).
- No secrets in the diff.
- Report what was verified and what remains unknown.

## Source of truth (pointers)

- Architecture: [docs/architecture.md](docs/architecture.md)
- Deploy: [docs/deployment.md](docs/deployment.md)
- **Full audit (cloud, multi-user, risks):** [docs/audits/2026-10-10-full-codebase-analysis.md](docs/audits/2026-10-10-full-codebase-analysis.md)
- **Chat/skill wishlist (impl TBD):** [docs/audits/2026-10-10-desired-features-from-chats.md](docs/audits/2026-10-10-desired-features-from-chats.md)
- Formula: [docs/formula-v4.md](docs/formula-v4.md), [docs/formula-v5.md](docs/formula-v5.md)
- ESPN MCP: [tools/espn-mcp/README.md](tools/espn-mcp/README.md)

## Cloud Day-0 defaults (household)

- Three services: Cloudflare Pages (web) + Railway API + Railway `espn-mcp-http` — do not merge API and MCP.
- Decent security first: secrets in platform env, MCP bearer/OAuth, CORS allowlist; harden API auth in Phase-1.
- No Postgres until multi-device draft sync or accounts are required.
- `.cursor/` is gitignored — do not rely on local skills/MCP config being in git.

## Prune

Review this file when commands or layout change. Prefer fixing CI/linters over adding prose rules.
