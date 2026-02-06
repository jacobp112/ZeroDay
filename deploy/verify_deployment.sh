#!/bin/bash
set -e

BASE_URL=${API_BASE_URL:-"https://staging-api.parsefin.io"}

echo "Verifying Deployment at $BASE_URL..."

# 1. Health Check
echo "Checking API Health..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/health")
if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: Health check failed with $HTTP_CODE"
    exit 1
fi

# 2. Run E2E Script
echo "Running E2E Verification..."
# We point the python script to staging
export API_BASE_URL=$BASE_URL
python scripts/verify_phase2_auto.py

echo "Verification Successful!"
