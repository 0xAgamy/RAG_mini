#!/bin/sh

set -e

echo "[INFO] Running Database Migration......"

alembic -c /app/models/db_schemes/ragdb/alembic.ini upgrade head
echo "[INFO] Alembic exit code: $?"


echo "[INFO] Database Migration Succesfully......"

cd /app
exec "$@"
