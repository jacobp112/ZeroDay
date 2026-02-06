# Multi-Tenancy Migration Guide

## Prerequisites
- PostgreSQL 14+ with RLS support
- Database backup created
- Downtime window scheduled (20-30 minutes)

## Steps
1. **Backup database**:
   ```bash
   pg_dump $DATABASE_URL -F c -b -v -f "full_backup.dump"
   ```
2. **Apply schema migration**:
   ```bash
   python -m alembic upgrade head
   ```
3. **Run data migration**:
   ```bash
   python scripts/migrate_to_multi_tenancy.py
   ```
4. **Verify RLS**:
   ```bash
   psql $DATABASE_URL -c "SELECT relname, relrowsecurity FROM pg_class WHERE relname='jobs';"
   ```
5. **Generate API keys**:
   ```bash
   curl -X POST http://localhost:8000/admin/tenants/{legacy_id}/api-keys ...
   ```

## Verification
- [ ] All jobs have `tenant_id` and `organization_id`
- [ ] RLS policies active (`relrowsecurity = t`)
- [ ] Cross-tenant access blocked (Returns 0 rows or 404)

## Rollback
If issues occur:
```bash
python -m alembic downgrade <previous_revision>
```
Or MANUAL disable:
```sql
ALTER TABLE jobs DISABLE ROW LEVEL SECURITY;
```
