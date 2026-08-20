#!/bin/sh
set -e

mkdir -p /app/data /app/logs

if [ "$(id -u)" = "0" ]; then
    chown -R app:app /app/data /app/logs
    exec gosu app "$@"
fi

exec "$@"
