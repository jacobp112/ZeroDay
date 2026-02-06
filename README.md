# ParseFin Enterprise API

A scalable, secure, multi-tenant brokerage statement parsing system with async job processing.

## 🚀 Key Features

- **Multi-Tenancy**: Database-enforced isolation (Row-Level Security) for strict data segregation.
- **Async Processing**: Scalable Celery workers for handling large PDF parsing jobs.
- **Enterprise Security**: Bcrypt API key hashing, Immutable Audit Logs, and Tenant Context injection.
- **Parsing Engine**: Hybrid extraction using Regex, Spatial Analysis, and LLM fallbacks.

## 📚 Documentation

Detailed guides for operations and security:

- [Migration Guide](docs/MIGRATION_GUIDE.md): Upgrading to Multi-Tenancy.
- [Tenant Management](docs/TENANT_MANAGEMENT.md): Onboarding customers and rotating keys.
- [Security Architecture](docs/SECURITY_ARCHITECTURE.md): Deep dive into RLS and Threat Models.

## 🛠️ Architecture

- **API**: FastAPI (Async/Await) with `TenantContextMiddleware`
- **Worker**: Celery (Distributed Processing)
- **Broker**: Redis
- **Database**: PostgreSQL 15+ (RLS Enabled)
- **Storage**: S3 / MinIO (PDFs & JSON Reports)

## ⚡ Quick Start (Docker)

### 1. Start the Stack
```bash
docker-compose up -d --build
```
Ensure `.env` matches your environment (see `.env.example`).

### 2. Run Database Migrations
Initialize schema and enable RLS policies:
```bash
docker-compose exec api alembic upgrade head
```
*Note: For production migration of existing data, see [Migration Guide](docs/MIGRATION_GUIDE.md).*

### 3. Create a Tenant (Admin)
Since RLS is enabled, you must create a tenant to generate an API key.
```bash
# 1. Create Organization
curl -X POST http://localhost:8000/admin/organizations \
  -H "X-API-Key: <ADMIN_KEY>" \
  -d '{"name": "Demo Corp", "slug": "demo"}'

# 2. Create Tenant
curl -X POST http://localhost:8000/admin/organizations/<ORG_ID>/tenants \
  -H "X-API-Key: <ADMIN_KEY>" \
  -d '{"name": "Demo Division", "slug": "demo-div"}'

# 3. Generate API Key
curl -X POST http://localhost:8000/admin/tenants/<TENANT_ID>/api-keys \
  -H "X-API-Key: <ADMIN_KEY>" \
  -d '{"name": "Dev Key", "reason": "Initial setup"}'
```
*Save the returned API Key (starts with `ak_`).*

### 4. Submit a Job
```bash
curl -X POST "http://localhost:8000/v1/parse" \
  -H "X-API-Key: ak_..." \
  -F "file=@sample.pdf"
```

### 5. Check Status
```bash
curl -H "X-API-Key: ak_..." "http://localhost:8000/v1/jobs/<job_id>"
```

## 🔒 Security & RLS

Multi-Tenancy is enforced at the database level using PostgreSQL Row-Level Security.

- **Isolation**: Tenant A cannot query Tenant B's jobs, even with SQL Injection.
- **Authentication**: All requests require `X-API-Key`.
- **Audit**: Admin actions (cross-tenant) are logged to `admin_audit_log` (Append-Only).

To monitor security events:
```bash
./scripts/monitor_tenant_isolation.sh
```

## 🧪 Development & Testing

Run the full suite including isolation tests:
```bash
# Verify Tenant Isolation
python -m pytest tests/test_tenant_isolation.py -v

# Run all tests
python -m pytest tests/
```

- **Monitoring**: [http://localhost:5555](http://localhost:5555) (Flower)
- **Metrics**: [http://localhost:9090](http://localhost:9090) (Prometheus)
