# Deployment

## Web

Build `apps/web` with `VITE_API_BASE_URL` set to the public API origin and deploy
the generated `dist` directory to Cloudflare Pages. Configure all unknown routes
to return `index.html`, and do not strip the service worker, wheel, or Pyodide
assets from the output.

## API

Build `apps/api/Dockerfile` from the repository root and deploy it to Railway.
Set:

- `FANTASY_DRAFT_CORS_ORIGINS` to the exact web origins, comma-separated.
- `FANTASY_DRAFT_LOG_LEVEL` to the desired log level.

Keep at least one API instance warm during live drafts if the hosting plan
otherwise sleeps idle services. Verify `/health` after each deployment.

## Release check

Run Python tests and type/lint checks, frontend unit tests and production build,
then the Playwright offline scenario. Finally perform the steps in
[offline-readiness.md](offline-readiness.md) against the deployed application.

No server database is required for the MVP. When accounts are introduced, add
PostgreSQL migrations before enabling synchronization and retain client export
and recovery paths.
