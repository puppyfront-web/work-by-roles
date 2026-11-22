#!/bin/sh
set -eu
i=0
until alembic upgrade head; do
  i=$((i + 1))
  if [ "$i" -ge 10 ]; then
    exit 1
  fi
  sleep 2
done
exec "$@"
