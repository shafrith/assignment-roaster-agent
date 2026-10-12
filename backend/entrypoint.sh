#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

# Behind a reverse proxy, uvicorn must trust X-Forwarded-For/-Proto from the proxy ONLY, or
# every client shares the proxy's IP (one global rate-limit bucket) — SEC-4.
# FORWARDED_ALLOW_IPS: comma-separated IPs (or CIDRs, uvicorn >= 0.32) of your proxy (e.g. "172.18.0.0/16" for a
# Docker network, or the LB's subnet). Never "*" when the port is reachable directly: clients
# could then spoof X-Forwarded-For and dodge rate limits.
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
if [ "$FORWARDED_ALLOW_IPS" = "*" ]; then
    echo "WARNING: FORWARDED_ALLOW_IPS='*' trusts X-Forwarded-For from anyone (spoofable)." >&2
fi

echo "Starting API server (trusting forwarded headers from: ${FORWARDED_ALLOW_IPS})..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}" \
    --no-server-header
