#!/bin/bash
set -e

# Load Env
source .env

echo "Deploying Application..."

# 1. Pull Code
echo "Pulling latest code..."
git pull origin main

# 2. Build Frontend
echo "Building Frontends..."
# Admin
cd frontend/admin
npm ci
npm run build
cd ../..

# Portal
cd frontend/portal
npm ci
npm run build
cd ../..

# 3. Update Containers
echo "Updating Docker Containers..."
docker compose build
docker compose up -d

# 4. Prune Old Images
echo "Pruning old images..."
docker image prune -f

echo "Deployment Complete."
./deploy/verify_deployment.sh
