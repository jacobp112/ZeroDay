#!/bin/bash
set -e

echo "Starting Rollback..."

# 1. Revert Git
echo "Reverting to previous commit..."
# Assuming we want to go back 1 commit or to a specific tag passed as arg
TARGET=${1:-"HEAD^"}
git reset --hard $TARGET

# 2. Rebuild Frontend
echo "Rebuilding Frontends..."
cd frontend/admin && npm ci && npm run build && cd ../..
cd frontend/portal && npm ci && npm run build && cd ../..

# 3. Restart Containers
echo "Restarting Containers..."
docker compose up -d --build

echo "Rollback Complete. Database state was NOT reverted automatically."
echo "If database migration rollback is needed, run: docker compose exec api python -m alembic downgrade -1"
