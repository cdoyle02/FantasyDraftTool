# Build from repository root:
#   docker build -f apps/web/Dockerfile --build-arg VITE_API_BASE_URL=https://api.example .
#
# Produces a static Vite PWA (engine wheel + Pyodide) served by Caddy with SPA fallback.

FROM ghcr.io/astral-sh/uv:0.9.7 AS uv

FROM node:20-bookworm-slim AS build

COPY --from=uv /uv /usr/local/bin/uv

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

WORKDIR /app

# JS deps first for layer caching
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile

# Offline DVS wheel (gitignored; required before vite build)
COPY packages/dvs-engine packages/dvs-engine
RUN pnpm build:engine

COPY apps/web apps/web

ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm --filter @fantasy-draft-tool/web build

FROM caddy:2-alpine

COPY apps/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/apps/web/dist /srv

EXPOSE 8080
