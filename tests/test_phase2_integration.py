import pytest
import uuid
from fastapi.testclient import TestClient
from brokerage_parser.api import app
from brokerage_parser.models.tenant import Organization, Tenant
from brokerage_parser.models.provisioning import ProvisioningRequest, ProvisioningStatus

client = TestClient(app)

def test_full_provisioning_flow(db_session):
    # 1. Start Provisioning via Admin API

    # Override Admin Auth
    from brokerage_parser.auth.admin import get_current_admin
    from brokerage_parser.models.admin import AdminUser
    from sqlalchemy import text

    def mock_admin():
        db_session.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        return AdminUser(email="superadmin@example.com", role="superadmin", is_active=True)

    app.dependency_overrides[get_current_admin] = mock_admin

    suffix = str(uuid.uuid4())[:8]
    payload = {
        "org_name": f"Integration Org {suffix}",
        "org_slug": f"integration-org-{suffix}",
        "admin_email": f"integration-{suffix}@test.com"
    }

    response = client.post("/admin/provisioning", json=payload)
    assert response.status_code == 202
    req_data = response.json()
    assert req_data["org_slug"] == f"integration-org-{suffix}"
    request_id = req_data["request_id"]

    # 2. Process Task (Synchronously for test)
    from brokerage_parser.provisioning import tasks as provisioning_tasks

    # Patch SessionLocal to use our db_session which has RLS set
    db_session.execute(text("SELECT set_config('app.is_admin', 'true', false)"))

    original_session_local = provisioning_tasks.SessionLocal
    provisioning_tasks.SessionLocal = lambda: db_session

    try:
        provisioning_tasks.provision_tenant_task(request_id) # Run sync
    finally:
        provisioning_tasks.SessionLocal = original_session_local

    # 3. Check Status
    response = client.get(f"/admin/provisioning/{request_id}")
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["status"] == "COMPLETED", f"Provisioning failed: {status_data.get('error_message')}"

    # 4. Verify Resources
    org_id = status_data["result_data"]["organization_id"]
    response = client.get("/admin/organizations")
    assert response.status_code == 200
    orgs = response.json()
    assert any(o["organization_id"] == org_id for o in orgs)

    # 5. Verify Rate Limits (Default)
    tenant_id = status_data["result_data"]["tenant_id"]
    # Currently we return 404 if not set, or create defaults on read?
    response = client.get(f"/admin/tenants/{tenant_id}/rate-limits")
    assert response.status_code == 404 # As expected initially

    # Create Limits
    limits_update = {
        "jobs_per_hour": 100
    }
    response = client.patch(f"/admin/tenants/{tenant_id}/rate-limits", json=limits_update)
    assert response.status_code == 200
    assert response.json()["jobs_per_hour"] == 100

    # 6. Verify Usage History (Empty)
    response = client.get(f"/admin/tenants/{tenant_id}/usage-history")
    assert response.status_code == 200
    assert response.json() == []

    # Cleanup overrides
    app.dependency_overrides = {}
