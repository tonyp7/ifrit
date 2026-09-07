#!/bin/bash
# Container entrypoint — starts uvicorn (backend) and nginx (static frontend +
# reverse proxy) together in this one container, per
# specs/architecture/infra.md § Containerisation ("supervised by a lightweight
# process manager or entrypoint script" — this is the entrypoint-script option,
# deliberately not pulling in supervisord/s6 for just two processes).
#
# bash (not /bin/sh) specifically for `wait -n` below — Debian's default dash
# doesn't support it, but bash ships in python:3.12-slim-trixie by default.
set -euo pipefail

# Idempotent — alembic no-ops if already at head — so it's safe to run on every
# container start rather than requiring a separate manual migration step. See
# specs/architecture/infra.md § Deployment.
alembic upgrade head

# Bound to localhost only: nginx is the sole caller, from inside this same
# container (see docker/nginx.conf's /api/ location) — never exposed directly.
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

nginx -g 'daemon off;' &
NGINX_PID=$!

# If either process dies, tear down the other and exit — so `docker stop`/a
# crashed child both result in the whole container stopping, not a half-alive
# one left behind.
trap 'kill -TERM "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true' TERM INT

wait -n "$UVICORN_PID" "$NGINX_PID"
EXIT_CODE=$?
kill -TERM "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
exit "$EXIT_CODE"
