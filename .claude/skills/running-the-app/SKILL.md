---
name: running-the-app
description: Use when asked to run, start, launch, preview, or demo the Fantasy Draft Tool locally, or to verify a code change actually works in the running app (not just passing tests).
---

# Running the App

## Overview

Two services run together: a FastAPI backend (`apps/api`, using `packages/dvs-engine`) on `:8000`, and a Vite/React frontend (`apps/web`) on `:5173`. JS deps are managed by pnpm, Python deps by uv. See root `CLAUDE.md` for architecture details.

## Prerequisites check

```bash
which pnpm || (corepack enable && corepack prepare pnpm@latest --activate)  # pnpm often isn't preinstalled even when node is
which uv                                    # https://docs.astral.sh/uv if missing
lsof -i :8000 -sTCP:LISTEN                  # already running? skip step 2
lsof -i :5173 -sTCP:LISTEN                  # already running? skip step 3
```

## Steps

1. Install deps (first run, or after a lockfile change):
   ```bash
   pnpm install
   uv sync --all-packages --all-groups
   ```
2. Start the API in the background:
   ```bash
   pnpm api:dev > /tmp/fdt-api.log 2>&1 &
   disown
   ```
   Ready when the log shows `Application startup complete.` — serves `http://127.0.0.1:8000`.
3. Start the web app in the background:
   ```bash
   pnpm dev > /tmp/fdt-web.log 2>&1 &
   disown
   ```
   Ready when the log shows `ready in ... ms` — serves `http://localhost:5173`.
4. Verify it actually works, don't just check ports:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs   # expect 200
   curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/      # expect 200 (proves shell loaded, not the app)
   ```
   Then load `http://localhost:5173` with the chrome-devtools MCP (`new_page` + `take_screenshot`) and confirm the draft board renders real player recommendations — a 200 on `/` only proves the empty HTML shell loaded.

## Notes / gotchas

- No `apps/web/.env.local` needed locally — `apps/web/src/api/client.ts` defaults `VITE_API_BASE_URL` to `http://localhost:8000` whenever `import.meta.env.DEV` is true.
- A banner reading *"Offline Python engine is not ready: Failed to execute 'importScripts'..."* is expected and harmless while online. It's the Pyodide/offline fallback path, which needs `pnpm build:engine` (builds the `dvs-engine` wheel into `apps/web/public/engine`) before it will work. Not required for normal online dev.
- To stop both servers (they were started with `disown`, so they're not shell job-control jobs): `` kill $(lsof -ti :8000 -sTCP:LISTEN) $(lsof -ti :5173 -sTCP:LISTEN) ``.

## Common mistakes

- Assuming pnpm is already on `PATH` because node is installed — it usually needs `corepack enable` first.
- Treating a `200` on `http://localhost:5173/` as proof the SPA works — it only proves the static shell loaded; check the rendered DOM/screenshot for real data.
- Running `pnpm install`/`uv sync` again on every launch — skip them once `node_modules` and the uv env already exist and the lockfiles haven't changed.
