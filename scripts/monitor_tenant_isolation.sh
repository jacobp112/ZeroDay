#!/bin/bash
# Monitor for RLS violations and security events

while true; do
  echo "=== Tenant Isolation Health Check ==="
  echo "Time: $(date)"

  # Check for RLS policy violations in logs
  echo "Recent RLS-related errors:"
  # Note: Adjust log path for your specific environment (e.g. Docker logs)
  tail -100 /var/log/parsefin/api.log 2>/dev/null | grep -i "rls\|tenant\|isolation" | tail -5

  # Check admin audit log growth
  echo "Admin actions in last hour:"
  psql $DATABASE_URL -c "
    SELECT count(*) as admin_actions
    FROM admin_audit_log
    WHERE timestamp > NOW() - INTERVAL '1 hour';
  "

  # Check for orphaned jobs (should be 0)
  echo "Jobs without tenant_id (should be 0):"
  psql $DATABASE_URL -c "
    SELECT count(*) FROM jobs WHERE tenant_id IS NULL;
  "

  # Check active tenants
  echo "Active tenants:"
  psql $DATABASE_URL -c "
    SELECT count(*) as active_tenants FROM tenants WHERE is_active = true;
  "

  sleep 300  # Check every 5 minutes
done
