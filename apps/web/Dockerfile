# Build from repository root:
#   docker build -f apps/web/Dockerfile --build-arg VITE_API_BASE_URL=https://api.example .
#
# Produces a static Vite PWA (engine wheel + Pyodide) served by Caddy with SPA fallback.

# Pure-Python wheel without uv downloading a standalone CPython (flaky on Railway).
FROM python:3.13-slim AS engine
WORKDIR /build
COPY packages/dvs-engine /build/dvs-engine
RUN pip install --no-cache-dir build \
	&& python -m build --wheel --outdir /out /build/dvs-engine

FROM node:20-bookworm-slim AS build

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app

# JS deps first for layer caching
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile

# Offline DVS wheel (gitignored; required before vite build)
RUN mkdir -p apps/web/public/engine
COPY --from=engine /out/*.whl apps/web/public/engine/

COPY apps/web apps/web

ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm --filter @fantasy-draft-tool/web build

FROM caddy:2-alpine

COPY apps/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/apps/web/dist /srv

EXPOSE 8080
