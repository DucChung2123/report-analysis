#!/bin/bash
set -e

# echo "Waiting for PostgreSQL..."
# while ! pg_isready -h db -p 5432 -U postgres; do
#   sleep 1
# done

cd /app

echo "Checking for existing migrations..."
if [ -z "$(ls -A migrations/alembic/versions/ 2>/dev/null)" ]; then
  echo "No migration files found. Creating initial migration..."
  alembic -c migrations/alembic.ini revision --autogenerate -m "Initial migration"
fi

echo "Running migrations..."
alembic -c migrations/alembic.ini upgrade head

echo "Starting application..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload