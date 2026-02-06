#!/bin/bash
set -e

# Load Env
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
else
    echo "Error: .env file not found"
    exit 1
fi

echo "Initializing Database..."

# 1. Wait for DB
echo "Waiting for PostgreSQL..."
until docker compose exec -T db pg_isready; do
  echo "  Retrying..."
  sleep 2
done

# 2. Run Migrations
echo "Running Alembic Migrations..."
docker compose exec -T api python -m alembic upgrade head

# 3. Create Admin User (Idempotent check inside script ideally, or catch error)
echo "Creating First Admin User..."
# Pass credentials via env vars or args if script supports it
# Assuming create_first_admin.py reads env vars
docker compose exec -T api python scripts/create_first_admin.py || echo "Admin user creation skipped (failed or exists)"

# 4. Seed Test Data (Optional for Staging)
if [ "$ENVIRONMENT" == "staging" ]; then
    echo "Seeding Staging Data..."
    # Add seeding logic here
fi

echo "Database Initialized."
