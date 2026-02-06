# ParseFin Enterprise API

A secure, multi-tenant brokerage statement parsing platform featuring administrative control, customer self-service, and comprehensive monitoring infrastructure.

## Core Features

- **Multi-Tenancy**: Data isolation enforced via PostgreSQL Row-Level Security (RLS) for absolute segregation of tenant data.
- **Administrative Control Plane**: Centralized management of organizations, tenants, and API keys with mandatory audit logging for all state-changing operations.
- **Customer Self-Service Portal**: Scoped interface for tenants to manage their own API keys, view usage metrics, and monitor job statuses.
- **Enterprise Security**: Standardized Bcrypt hashing for API keys, secure JWT-scoped authentication, and automated audit trails.
- **Monitoring and Observability**: Deep integration with Prometheus and Grafana for real-time telemetry on system performance and per-tenant activity.
- **Parsing Engine**: Tiered extraction logic combining Regex, spatial analysis, and LLM-assisted verification.

## Documentation Links

For detailed operational and design specifications, refer to the following documents:

- [Security Architecture](docs/SECURITY_ARCHITECTURE.md): Technical overview of RLS implementation and threat modeling.
- [Tenant Management Guide](docs/TENANT_MANAGEMENT.md): Procedures for organization onboarding and key rotation.
- [Phase 1 Walkthrough](C:/Users/c23052656/.gemini/antigravity/brain/7c60da5a-5d0a-4f37-b082-7eb7ee6a7e4f/walkthrough.md): Detailed verification results and implementation status.

## Technical Stack

- **Application Layer**: FastAPI (Async/Await) with SQLAlchemy 2.0 ORM.
- **Data Persistence**: PostgreSQL 15+ with native RLS support.
- **Distributed Processing**: Celery workers with Redis as the message broker.
- **Monitoring**: Prometheus (Metrics collection) and Grafana (Visualization).
- **Frontend Infrastructure**: React (Vite-based) for both Admin and Customer portals.

## Quick Start (Local Deployment)

### 1. Environment Configuration
Copy the template and configure the required environment variables:
```bash
cp .env.example .env
```

### 2. Infrastructure Initialization
Deploy the core services using Docker:
```bash
docker-compose up -d --build
```

### 3. Database Schema Provisioning
Apply Alembic migrations to initialize the schema and RLS policies:
```bash
docker-compose exec api alembic upgrade head
```

### 4. Administrative Onboarding
Bootstrap the initial administrative user and provision the first organization:
```bash
python scripts/create_first_admin.py
```

## Security and Isolation

Multi-tenancy is not just an application-level filter but is enforced at the database level:

1.  **Strict Isolation**: RLS policies prevent cross-tenant data access, even in the event of application-layer vulnerabilities.
2.  **Audit Enforcement**: All administrative actions affecting system state are recorded in immutable logs.
3.  **Scoped Identity**: Tenant-facing JWTs are strictly scoped to specific `tenant_id` and `organization_id` claims.

## Verification

To validate system integrity and tenant isolation, execute the end-to-end verification suite:

```bash
python scripts/verify_phase1_e2e.py
```

## System Dashboards

- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Monitoring Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **Grafana Visualization**: [http://localhost:3000](http://localhost:3000)
- **Task Monitoring (Flower)**: [http://localhost:5555](http://localhost:5555)
