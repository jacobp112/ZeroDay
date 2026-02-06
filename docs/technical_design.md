# Technical Design: Operational Excellence (Phase 2)

This document provides a deep-dive technical overview and architectural visualization of the features implemented in Phase 2.

## 1. System Architecture Overview

Phase 2 transformed the system from a simple parser into a scalable SaaS platform by introducing asynchronous processing and high-performance state management.

### Deployment Architecture
The following diagram illustrates the containerized micro-services architecture deployed in Phase 2.

```mermaid
graph TB
    subgraph "Public Internet"
        Client[Client / Browser]
    end

    subgraph "Private Network (Docker Compose)"
        LB[Nginx Reverse Proxy]

        subgraph "Application Layer"
            API[FastAPI Server]
            Worker[Celery Worker]
            Beat[Celery Beat]
        end

        subgraph "Data Layer"
            Redis[(Redis Cache & Queue)]
            DB[(PostgreSQL DB)]
        end

        subgraph "Monitoring Layer"
            Prom[Prometheus]
            Graf[Grafana]
        end
    end

    Client -->|HTTPS| LB
    LB -->|HTTP:8000| API

    API -->|Read/Write| Redis
    API -->|Read/Write| DB

    API -->|Push Task| Redis
    Redis -->|Pop Task| Worker
    Beat -->|Schedule| Redis

    Worker -->|Process| DB

    Prom -->|Scrape Metrics| API
    Prom -->|Scrape Metrics| Worker
    Graf -->|Query| Prom
```

---

## 2. Database Schema (ERD)

Phase 2 introduced tenancy management and metering tables.

```mermaid
erDiagram
    organizations ||--|{ tenants : owns
    organizations ||--|{ users : has
    tenants ||--|{ usage_events : generates
    tenants ||--|{ usage_records : aggregates
    tenants ||--o| tenant_rate_limits : configured_by
    tenants ||--|{ api_keys : uses

    provisioning_requests ||--|{ organizations : creates
    provisioning_requests ||--|{ tenants : creates

    organizations {
        uuid id PK
        string slug "Unique"
        string name
        string billing_email
    }

    tenants {
        uuid id PK
        uuid organization_id FK
        string slug "Unique"
        string name
    }

    tenant_rate_limits {
        uuid tenant_id PK, FK
        int requests_per_minute
        int jobs_per_hour
        int concurrent_jobs
    }

    usage_events {
        uuid id PK
        uuid tenant_id FK
        string event_type "JOB_SUBMITTED, etc."
        float quantity
        jsonb metadata
        timestamp created_at
    }

    usage_records {
        uuid id PK
        uuid tenant_id FK
        date date
        int jobs_count
        float storage_mb
    }

    provisioning_requests {
        uuid request_id PK
        string status "PENDING, COMPLETED, FAILED"
        jsonb payload
        string error_message
    }
```

---

## 3. Request Processing Pipeline

Every API request flows through a strict middleware pipeline to ensure security and resource governance.

```mermaid
sequenceDiagram
    participant C as Client
    participant N as Nginx
    participant M1 as TrustedHostMiddleware
    participant M2 as RateLimitMiddleware
    participant M3 as AuthMiddleware
    participant EP as Endpoint
    participant DB as Database (RLS)

    C->>N: Request
    N->>M1: Forward to FastAPI
    M1->>M2: Validate Host

    Note over M2: Check Redis Sliding Window
    alt Rate Limit Exceeded
        M2-->>C: 429 Too Many Requests
    else Allowed
        M2->>M3: Pass Request
    end

    Note over M3: Verify JWT or API Key
    alt Invalid Auth
        M3-->>C: 401 Unauthorized
    else Valid Auth
        M3->>EP: Set Request.User / Request.Tenant
    end

    EP->>DB: Set RLS Context (set_config)
    EP->>DB: Execute Query
    DB-->>EP: Result (Filtered by RLS)
    EP-->>C: JSON Response
```

---

## 4. Rate Limiting: Sliding Window Algorithm

We implemented a **Sliding Window** rate limiting algorithm using Redis Sorted Sets (`ZSET`). This provides higher accuracy than fixed windows.

### Algorithm Logic
1.  **Key**: `ratelimit:{tenant_id}:{limit_type}` (e.g., `requests_per_minute`)
2.  **Clean up**: `ZREMRANGEBYSCORE` removes timestamps older than the window (e.g., `now - 60s`).
3.  **Count**: `ZCARD` returns the number of requests currently in the window.
4.  **Decide**:
    - If `count < limit`: `ZADD` current timestamp and allow.
    - If `count >= limit`: Block request.

### Implementation Detail (`rate_limiter.py`)
```mermaid
flowchart TD
    Start(Incoming Request) -->|Extract TenantID| GetLimits[Fetch Limits from DB/Cache]
    GetLimits --> CheckRedis{Check Redis ZSET}

    CheckRedis -->|Clean Old Entries| Clean[ZREMRANGEBYSCORE]
    Clean --> Count[ZCARD]

    Count --> Decision{Count < Limit?}

    Decision -- Yes --> Add[ZADD Timestamp]
    Add --> Allow[Forward Request]

    Decision -- No --> Block[Return 429]
    Block -->|Retry-After Header| End
```

---

## 5. Usage Metering Pipeline

The metering system uses a "Capture & Aggregate" pattern to handle high write throughput without locking the reporting tables.

```mermaid
graph LR
    subgraph "Real-Time Capture"
        API[API Endpoint] -->|1. Event| Collector[UsageCollector]
        Worker[Celery Worker] -->|1. Event| Collector
        Collector -->|2. BUFFER/INSERT| Events[(usage_events Table)]
    end

    subgraph "Async Aggregation (Hourly)"
        Beat[Celery Beat] -->|3. Trigger| AggTask[aggregate_daily_usage]
        AggTask -->|4. SELECT SUM()| Events
        AggTask -->|5. UPSERT| Records[(usage_records Table)]
    end
```

---

## 6. Automated Application Provisioning

The provisioning workflow orchestrates the creation of all necessary resources for a new customer in a single atomic operation (logically) with rollback capabilities.

### Workflow Logic
```mermaid
stateDiagram-v2
    [*] --> PENDING: Admin submits form
    PENDING --> PROCESSING: Celery Task Started

    state PROCESSING {
        direction TB
        Step1: Create Organization
        Step2: Create Tenant
        Step3: Generate API Keys
        Step4: Configure Defaults (Rate Limits)
        Step5: Send Welcome Email

        Step1 --> Step2
        Step2 --> Step3
        Step3 --> Step4
        Step4 --> Step5
    }

    PROCESSING --> COMPLETED: All Steps Success
    PROCESSING --> FAILED: Any Error

    FAILED --> ROLLBACK: Transaction Rollback
    ROLLBACK --> [*]: Data Cleaned

    COMPLETED --> EMAIL: Notify Admin
    EMAIL --> [*]
```

### Class Structure (`provisioning/workflow.py`)
```mermaid
classDiagram
    class ProvisioningWorkflow {
        +db: Session
        +provision_tenant(request_id)
        -create_organization()
        -create_tenant()
        -generate_keys()
        -send_email()
    }

    class ProvisioningRequest {
        +uuid request_id
        +string organization_name
        +string admin_email
        +string status
    }

    ProvisioningWorkflow --> ProvisioningRequest : processes
```

---

## 7. Email Service with Fallback

To ensure reliability even without a configured email provider (e.g., in dev/staging), we implemented a database fallback pattern.

```mermaid
flowchart TD
    Start(Send Email Request) --> Configcheck{Provider Configured?}

    Configcheck -- Yes (SMTP/AWS) --> Send[Attempt Send]
    Send --> Success{Sent?}

    Success -- Yes --> Log[Log Info]
    Success -- No --> Fallback

    Configcheck -- No --> Fallback[Save to pending_notifications]

    Fallback --> DB[(Database)]
    DB --> AdminUI[Admin Dashboard Alert]
```

---

## 8. Monitoring & Observability

We integrated Prometheus metrics to track the health of these new systems.

### Key Metrics
| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `parselib_rate_limit_exceeded_total` | Counter | Number of 429 responses returned. |
| `parselib_usage_events_total` | Counter | Number of usage events recorded. |
| `parselib_provisioning_duration_seconds` | Histogram | Time taken to provision a new tenant. |
| `parselib_active_tenants` | Gauge | Current number of active tenants. |

### Grafana Dashboard Architecture
```mermaid
graph TD
    Prometheus -->|Query| RateLimitPanel[Rate Limit Panel]
    RateLimitPanel -->|Visualize| Graph1[429 vs 200 Requests]

    Prometheus -->|Query| UsagePanel[Usage Panel]
    UsagePanel -->|Visualize| Graph2[Jobs Processed / Hour]

    Prometheus -->|Query| SystemPanel[System Health]
    SystemPanel -->|Visualize| Graph3[CPU / Memory / Redis Latency]
```
