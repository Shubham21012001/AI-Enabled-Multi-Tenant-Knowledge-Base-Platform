#!/bin/sh
set -e
# Apply database migrations before the API starts (idempotent).
alembic upgrade head
exec "$@"
