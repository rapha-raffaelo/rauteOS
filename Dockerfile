# NewsPulse — dashboard + daily sweep in one image.
#
# The image carries the Claude Code CLI because analysis and Captain Comms both
# shell out to it (subscription-first, never an API key baked in). Its
# credentials are NOT in the image: they live in the config directory mounted at
# runtime, so the image holds no secret and can be rebuilt freely.
FROM node:22.22.3-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

# Use the same supported Node runtime for the AI CLI as for the frontend build.
# Debian's nodejs package can lag behind the CLI's minimum required version.
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# curl for the CLI installer and the healthcheck; ca-certificates so the feed
# fetches can verify TLS at all.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# The analyzer and the assistant both invoke `claude`; without it the sweep
# fails per batch and the drawer reports "CLI not found".
RUN npm install -g @anthropic-ai/claude-code && npm cache clean --force \
 && node --version && claude --version

# This file lives at the repository root, and the app lives in newspulse/, hence
# the prefixed COPY paths. It sits here so a PaaS that auto-detects a Dockerfile
# finds it with no configuration at all: an earlier layout kept it beside the app
# and depended on railway.json to point at it, which fails silently if the
# platform doesn't read that file. Building must not depend on config discovery.
# See .dockerignore for what the repo-root context excludes.
WORKDIR /app
COPY newspulse/pyproject.toml newspulse/uv.lock newspulse/README.md ./
COPY newspulse/src ./src
COPY --from=frontend /build/newspulse/src/newspulse/web/static/react ./src/newspulse/web/static/react
COPY newspulse/migrations ./migrations
COPY newspulse/alembic.ini ./

RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# The database is a single SQLite file and must outlive the container.
# Both the database and the CLI login live under one mount: a platform that
# gives a service a single volume (Railway) cannot attach two, and nothing is
# gained by separating them — they are lost together or kept together.
ENV NEWSPULSE_DATABASE_PATH=/data/newspulse.db \
    NEWSPULSE_WEB_HOST=0.0.0.0 \
    NEWSPULSE_CLAUDE_CONFIG_DIR=/data/claude

# Deliberately no `VOLUME /data`: Railway rejects the instruction outright
# ("docker VOLUME is not supported, use Railway Volumes") and the build fails to
# parse. It bought nothing anyway — an unmounted VOLUME creates an anonymous
# volume that is just as lost as a plain directory, only harder to find. The
# mount is declared where it is actually configured: a Railway volume at /data,
# or the bind mount in docker-compose.yml.
#
# The directory is created here so that an unmounted run still starts rather
# than failing on a missing path. That persists nothing — mount /data.
RUN mkdir -p /data
EXPOSE 8000

# Migrations run on start so a deploy never serves a schema older than its code.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run newspulse-web"]
