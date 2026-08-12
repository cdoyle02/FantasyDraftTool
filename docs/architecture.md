# Architecture

The application is local-first: the browser owns the active draft session, while
the API provides the normal online execution path for the Draft Value Score
(DVS) engine.

## Components

- `apps/web` is a React/TypeScript progressive web app. Zustand coordinates UI
  state and Dexie persists imports, adjustments, league settings, draft events,
  and events waiting to be synchronized.
- `apps/api` is a stateless FastAPI adapter. It validates HTTP requests and calls
  the engine; it does not contain scoring rules.
- `packages/dvs-engine` is the dependency-light Python domain package. Its JSON
  entrypoint runs in both CPython and Pyodide.

## Recommendation flow

The web engine adapter uses FastAPI while it is reachable. If a request fails or
the browser is offline, it sends the same JSON payload to a Pyodide Web Worker.
Keeping Python off the main browser thread prevents scoring from blocking manual
pick entry. Golden fixtures are evaluated in both runtimes to guard against
behavior drift.

## Draft state

Picks are immutable events with stable IDs. The current board and rosters are
derived from the ordered event stream. Corrections append or replace events
through explicit commands, and undo removes the most recent local event. This
model supports browser recovery, offline work, later cloud synchronization, and
Sleeper ingestion without introducing a second state shape.

Imported projection data and user opinions are stored separately. Re-importing a
new baseline therefore cannot erase boosts, fades, tier overrides, tags, or
notes.

## Future persistence

The MVP requires no account. A later synchronization service can persist users,
leagues, imports, adjustments, and draft events in PostgreSQL behind repository
interfaces. The DVS package remains unchanged because it accepts complete domain
values and performs no I/O.
