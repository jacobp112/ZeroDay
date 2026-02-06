# Tenant Management Guide

## Creating a New Tenant

### Step 1: Create Organization
```bash
curl -X POST http://api.parsefin.io/admin/organizations \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"name": "ACME Bank", "slug": "acme-bank"}'
```

### Step 2: Create Tenant (Division)
```bash
curl -X POST http://api.parsefin.io/admin/organizations/{org_id}/tenants \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"name": "London Branch", "slug": "london"}'
```

### Step 3: Generate API Key
```bash
curl -X POST http://api.parsefin.io/admin/tenants/{tenant_id}/api-keys \
  -H "X-API-Key: $ADMIN_KEY" \
  -d '{"name": "Production Key", "reason": "Customer onboarding"}'
```

**IMPORTANT:** Save the secret key immediately - it's only shown once.

## Rotating API Keys

1. Generate new key (Step 3 above)
2. Provide new key to customer
3. Allow 30-day grace period
4. Revoke old key: `curl -X DELETE .../api-keys/{key_id}`

## Troubleshooting

### Customer reports "404 Not Found" for their jobs
- Verify API key is active: `SELECT * FROM api_keys WHERE access_key_id = '...'`
- Check tenant_id matches: `SELECT tenant_id FROM jobs WHERE job_id = '...'`
- Verify RLS is not overly restrictive
