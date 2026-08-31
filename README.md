# Fantasy Draft Tool

A platform-independent, local-first fantasy football draft assistant. It
combines replacement value, positional tier cliffs, roster construction, and
configurable guardrails into explainable live recommendations.

The application is a React/TypeScript progressive web app backed by FastAPI.
The same pure-Python scoring package runs on the server and, through Pyodide, in
the browser when a draft loses internet access.

## Repository

- `apps/web` — live-draft PWA, browser persistence, and offline engine adapter
- `apps/api` — stateless FastAPI service
- `packages/dvs-engine` — deterministic Draft Value Score domain package
- `docs` — architecture, deployment, and draft-day readiness

## Prerequisites

- Node.js 20 or newer and pnpm 9
- Python 3.13 or newer and uv

## Development

```bash
pnpm install
uv sync --all-packages --all-groups
```

Start the API and web app in separate terminals:

```bash
pnpm api:dev
pnpm dev
```

Open `http://localhost:5173`. The API defaults to `http://localhost:8000`;
put `VITE_API_BASE_URL` in `apps/web/.env.local` to override the web client and
set the API variables from `.env.example` in the API process environment.

### Windows: `git pull` Permission denied on `.git/FETCH_HEAD`

On this machine, Git can fail with `cannot open '.git/FETCH_HEAD': Permission denied`
when the Windows Hidden attribute is set on files inside `.git`. That is usually
not a real ACL/lock problem. From the repo root in PowerShell or cmd:

```bat
attrib -h /s /d .git\*
attrib +h .git
```

Leave `.git` itself hidden. If the error comes back, a sandboxed process (for
example Codex sandbox SIDs on the file ACL) may be remounting the folder and
re-hiding files.

## Checks

```bash
uv run ruff check .
uv run mypy packages/dvs-engine/src apps/api/src
uv run pytest
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

The offline path needs a built DVS wheel and cached Pyodide distribution. See
[`docs/offline-readiness.md`](docs/offline-readiness.md) before relying on it in
a live draft.

## Product scope

Phase 1 targets full-PPR snake redraft leagues with configurable roster settings,
FantasyPros-style CSV imports, fast manual pick entry, persistent player
adjustments, and explainable recommendations. Opponent demand modeling, Sleeper
sync, simulations, and accounts are later phases.

## Default player pool

The web app ships a committed expert-pooled rankings seed (QB/RB/WR/TE/K/DST),
not the old 25-player demo. First visit loads it automatically. Existing
browsers still on the demo are upgraded in place. A **Load bundled rankings**
button replaces a CSV import without wiping boosts, fades, or tags.

Refresh the board by re-running the generator and rebuilding — there is no live
FantasyPros fetch in the app:

```bash
uv run python tools/rankings/generate.py
```

See [`tools/rankings/README.md`](tools/rankings/README.md). Set
`FANTASYPROS_API_KEY` in the environment, or drop exported CSVs in
`tools/rankings/inbox/`.
