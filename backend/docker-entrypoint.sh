#!/bin/sh
# Wait for the database, apply migrations (unless disabled), then exec the CMD.
# The worker sets TESQIVO_AUTO_MIGRATE=0 so only the web container migrates.
set -e

python -m app.cli wait-db

if [ "${TESQIVO_AUTO_MIGRATE:-1}" = "1" ]; then
    echo "applying database migrations..."
    alembic upgrade head
fi

exec "$@"
