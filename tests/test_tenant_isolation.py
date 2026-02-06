import pytest
import uuid
from sqlalchemy import text
from brokerage_parser.db import SessionLocal
from brokerage_parser.models import Job, JobStatus

# These tests assume RLS is ENABLED in the database.
# If running against local DB without RLS applied, they might fail or pass falsely.

from brokerage_parser.models import Organization, Tenant

@pytest.fixture(scope="function")
def setup_data():
    db = SessionLocal()
    # Create Org
    org_uid = uuid.uuid4()
    org = Organization(organization_id=org_uid, name="Test Org", slug=f"org-{org_uid}")
    db.add(org)

    # Create Tenant A
    ten_a_uid = uuid.uuid4()
    ten_a = Tenant(tenant_id=ten_a_uid, organization_id=org_uid, name="Tenant A", slug=f"tenant-{ten_a_uid}")
    db.add(ten_a)

    # Create Tenant B
    ten_b_uid = uuid.uuid4()
    ten_b = Tenant(tenant_id=ten_b_uid, organization_id=org_uid, name="Tenant B", slug=f"tenant-{ten_b_uid}")
    db.add(ten_b)

    db.commit()
    db.close()

    return {
        "org_id": str(org_uid),
        "tenant_a_id": str(ten_a_uid),
        "tenant_b_id": str(ten_b_uid)
    }

@pytest.fixture
def org_id(setup_data):
    return setup_data["org_id"]

@pytest.fixture
def tenant_a_id(setup_data):
    return setup_data["tenant_a_id"]

@pytest.fixture
def tenant_b_id(setup_data):
    return setup_data["tenant_b_id"]

@pytest.fixture
def db_session_tenant_a(tenant_a_id, org_id):
    db = SessionLocal()
    print(f"DEBUG: Setting TenantContext A: Tenant={tenant_a_id}, Org={org_id}")
    # Use set_config for safety. is_local=False means session duration.
    db.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": tenant_a_id})
    db.execute(text("SELECT set_config('app.current_organization_id', :oid, false)"), {"oid": org_id})

    # Verify
    res = db.execute(text("SELECT current_setting('app.current_tenant_id', true)")).scalar()
    print(f"DEBUG: Verify TenantID: '{res}'")

    yield db
    # Cleanup
    db.execute(text("RESET app.current_tenant_id"))
    db.execute(text("RESET app.current_organization_id"))
    db.close()

@pytest.fixture
def db_session_tenant_b(tenant_b_id, org_id):
    db = SessionLocal()
    print(f"DEBUG: Setting TenantContext B: Tenant={tenant_b_id}, Org={org_id}")
    db.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": tenant_b_id})
    db.execute(text("SELECT set_config('app.current_organization_id', :oid, false)"), {"oid": org_id})
    yield db
    db.execute(text("RESET app.current_tenant_id"))
    db.execute(text("RESET app.current_organization_id"))
    db.close()


def test_rls_isolation_jobs(db_session_tenant_a, db_session_tenant_b, tenant_a_id, tenant_b_id, org_id):
    # 1. Tenant A creates a job
    job_a = Job(
        client_id="client_a",
        status=JobStatus.PENDING,
        file_sha256="hash_a",
        file_s3_key="key_a",
        tenant_id=uuid.UUID(tenant_a_id),
        organization_id=uuid.UUID(org_id)
    )
    db_session_tenant_a.add(job_a)
    db_session_tenant_a.commit()
    job_a_id = job_a.job_id

    # 2. Tenant A can see it
    found_a = db_session_tenant_a.query(Job).get(job_a_id)
    assert found_a is not None
    assert str(found_a.tenant_id) == tenant_a_id

    # 3. Tenant B tries to see it
    # Even by ID query, RLS should filter it out -> returns None
    found_b = db_session_tenant_b.query(Job).get(job_a_id)
    assert found_b is None

    # 4. Tenant B creates a job
    job_b = Job(
        client_id="client_b",
        status=JobStatus.PENDING,
        file_sha256="hash_b",
        file_s3_key="key_b",
        tenant_id=uuid.UUID(tenant_b_id),
        organization_id=uuid.UUID(org_id)
    )
    db_session_tenant_b.add(job_b)
    db_session_tenant_b.commit()

    # 5. Tenant A cannot see Tenant B's job
    found_b_by_a = db_session_tenant_a.query(Job).get(job_b.job_id)
    assert found_b_by_a is None

def test_rls_insert_violation(db_session_tenant_a, tenant_b_id, org_id):
    # Try to insert a record for Tenant B while authenticated as Tenant A
    # The CHECK policy should prevent this.
    try:
        job_malicious = Job(
            client_id="hacker",
            status=JobStatus.PENDING,
            file_sha256="hash_hack",
            file_s3_key="key_hack",
            tenant_id=uuid.UUID(tenant_b_id), # Mismatched Tenant ID
            organization_id=uuid.UUID(org_id)
        )
        db_session_tenant_a.add(job_malicious)
        db_session_tenant_a.commit()
    except Exception as e:
        db_session_tenant_a.rollback()
        # Expecting RLS policy check violation
        assert "new row violates row-level security policy" in str(e) or "violates check constraint" in str(e) or "permission denied" in str(e).lower()
        return

    pytest.fail("Should have raised RLS violation error")

def test_rls_update_violation(db_session_tenant_a, tenant_a_id, org_id):
    # Insert valid job
    job = Job(
        client_id="client_a",
        status=JobStatus.PENDING,
        file_sha256="hash_up",
        file_s3_key="key_up",
        tenant_id=uuid.UUID(tenant_a_id),
        organization_id=uuid.UUID(org_id)
    )
    db_session_tenant_a.add(job)
    db_session_tenant_a.commit()

    # Try to change tenant_id to something else
    # UPDATE policy with CHECK should prevent moving rows between tenants
    try:
        job.tenant_id = uuid.uuid4()
        db_session_tenant_a.commit()
    except Exception as e:
        db_session_tenant_a.rollback()
        assert "new row violates row-level security policy" in str(e) or "violates check constraint" in str(e)
        return

    pytest.fail("Should have raised RLS violation error on update")
