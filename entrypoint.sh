#!/bin/sh
set -e

echo "[entrypoint] Running database migrations..."
flask db upgrade

echo "[entrypoint] Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:${PORT:-8000} run:app
