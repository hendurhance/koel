#!/bin/bash
set -e

# Wait for Postgres to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is up - continuing"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Seed database if needed
if [ "$SEED_DB" = "true" ]; then
  echo "Seeding database..."
  python -m app.db.seed
fi

# Execute the provided command
exec "$@"