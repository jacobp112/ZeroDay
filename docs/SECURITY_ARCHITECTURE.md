# Security Architecture: Multi-Tenancy with RLS

## Threat Model

### Threats Mitigated
1. **Cross-Tenant Data Access:** Database-enforced isolation prevents Tenant A from accessing Tenant B's data
2. **SQL Injection:** Even successful injection cannot bypass RLS policies
3. **Privilege Escalation:** Application-level bugs cannot circumvent database policies
4. **Insider Threats:** Admin actions are logged immutably to audit trail

### Defense in Depth Layers
1. **API Layer:** API key authentication, tenant context injection
2. **Application Layer:** Request validation, tenant scoping
3. **Database Layer:** RLS policies (FORCE mode), foreign key constraints
4. **Audit Layer:** Immutable append-only audit log

## RLS Policy Design

All data tables implement 4 policies:
- `SELECT`: `WHERE tenant_id = current_setting('app.current_tenant_id')::uuid`
- `INSERT`: `WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)`
- `UPDATE`: USING and WITH CHECK clauses prevent cross-tenant modifications
- `DELETE`: Restricted to owning tenant only

## Audit Requirements

All admin cross-tenant actions require:
- Authenticated admin role
- Mandatory `reason` field (business justification)
- Immutable log entry (cannot be deleted or modified)
- Retention: 7 years (2,555 days)

## Compliance

This architecture satisfies:
- ✅ SOC 2 Type II (Access Controls)
- ✅ ISO 27001 (Information Security)
- ✅ GDPR Article 32 (Security of Processing)
- ✅ PCI DSS (if handling payment card data)
