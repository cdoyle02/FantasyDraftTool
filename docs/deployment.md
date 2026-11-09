# Deployment

Household Day-0 runs three Railway services in one project (`fantasy-draft-mcp`):

| Service | Dockerfile / config | Role |
|---------|---------------------|------|
| `web` | [`apps/web/Dockerfile`](../apps/web/Dockerfile), [`apps/web/railway.toml`](../apps/web/railway.toml) | Vite PWA (engine wheel + Pyodide) via Caddy SPA fallback |
| `api` | [`apps/api/Dockerfile`](../apps/api/Dockerfile), [`apps/api/railway.toml`](../apps/api/railway.toml) | FastAPI recommendations + Week boards |
| `fantasy-draft-mcp` | [`tools/espn-mcp/Dockerfile`](../tools/espn-mcp/Dockerfile) | Hosted ESPN MCP (keep separate from the API) |

Do not merge the API and MCP into one service.

## Web

Build from the repository root with `VITE_API_BASE_URL` set to the public API
origin (Railway sets this as a build-time variable). The image runs `pnpm
build:engine` then the Vite production build, then serves `dist` with Caddy:

- Unknown routes fall back to `index.html` (SPA deep links).
- Do not strip the service worker, wheel, or Pyodide assets.
- `index.html` / `sw.js` / `manifest.webmanifest` are served with `Cache-Control: no-cache`.

Optional later move: the same `dist` output can be hosted on Cloudflare Pages;
set Pages build to produce the wheel (`uv` + `pnpm build:engine`) first.

## API

Build `apps/api/Dockerfile` from the repository root. Set:

- `FANTASY_DRAFT_CORS_ORIGINS` — exact web origin(s), comma-separated.
- `FANTASY_DRAFT_LOG_LEVEL` — desired log level (default `INFO`).
- `FANTASY_DRAFT_API_TOKEN` — household shared secret. When set, every
  `/api/v1/*` route except `/api/v1/health` and `/api/v1/version` requires
  header `X-Api-Token`. Leave unset for local/dev. The web app stores the
  matching value in `localStorage` key `fdt.apiToken` (never bake it into the
  bundle).
- Reuse ESPN / Odds secrets from the MCP service via Railway variable
  references (`${{fantasy-draft-mcp.ESPN_S2}}`, etc.) instead of pasting
  values twice.

Keep at least one API instance warm during live drafts if the hosting plan
otherwise sleeps idle services. Verify `/health` after each deployment.

## Release check

Run Python tests and type/lint checks, frontend unit tests and production build,
then the Playwright offline scenario. Finally perform the steps in
[offline-readiness.md](offline-readiness.md) against the deployed application.

No server database is required for the MVP. When accounts are introduced, add
PostgreSQL migrations before enabling synchronization and retain client export
and recovery paths.
