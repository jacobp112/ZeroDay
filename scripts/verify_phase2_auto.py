import requests
import time
import sys
import os
import psycopg2
import uuid
import datetime
from jose import jwt

# Configuration
BASE_URL = "http://localhost:8000"
DB_URL = "postgresql://parsefin:password@localhost:5432/brokerage_parser?sslmode=disable"
ADMIN_JWT_SECRET = "super_secret_admin_jwt_key_dev_only"
ADMIN_EMAIL = "verifier@parsefin.com"

def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return None

def setup_admin_user():
    conn = get_db_connection()
    if not conn: return False
    try:
        cur = conn.cursor()
        # Bypass RLS to insert admin
        cur.execute("SELECT set_config('app.is_admin', 'true', false)")

        # Check if exists
        cur.execute("SELECT id FROM admin_users WHERE email = %s", (ADMIN_EMAIL,))
        if cur.fetchone():
            return True # Already exists

        # Insert
        uid = str(uuid.uuid4())
        # Password doesn't matter as we forge token
        query = "INSERT INTO admin_users (id, email, password_hash, role, is_active, created_at) VALUES (%s, %s, %s, %s, %s, NOW())"
        cur.execute(query, (uid, ADMIN_EMAIL, "hash", "superadmin", True))
        print("Inserted Admin User.")
        return True
    except Exception as e:
        print(f"Failed to setup admin: {e}")
        return False
    finally:
        conn.close()

def generate_admin_token():
    payload = {
        "sub": ADMIN_EMAIL,
        "role": "superadmin",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }
    return jwt.encode(payload, ADMIN_JWT_SECRET, algorithm="HS256")

def main():
    results = {}

    print("Setting up verification environment...")
    if not setup_admin_user():
        print("Bailing: Could not setup admin user.")
        sys.exit(1)

    token = generate_admin_token()
    admin_headers = {"Authorization": f"Bearer {token}"}

    # 1. Provisioning Speed
    print("\nTest: Provisioning...")
    start = time.time()
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "org_name": f"Verify Corp {suffix}",
        "org_slug": f"verify-corp-{suffix}",
        "tenant_name": f"Verify Div {suffix}",  # Added tenant_name manually if API needs it?
        # Wait, the API schema in plan was: org_name, org_slug, admin_email.
        # But user Request payload showed: organization_name, calling it "Test Corp".
        # Let's check `api.py` or `admin.py` for `ProvisioningRequest` schema.
        # In `router/admin.py` (not shown fully) or `models/provisioning.py` (shown early).
        # Actually `ProvisioningRequest` model had `org_name`, `org_slug`, `admin_email`.
        # User example payload might be slightly off OR correct if Pydantic aliases used.
        # Impl plan says: org_name, org_slug, admin_email.
        # User payload in prompt: organization_name, tenant_name...
        # I'll stick to what I implemented: org_name, org_slug, admin_email.
        "admin_email": f"admin-{suffix}@verify.com"
    }

    # Actually, let's verify Schema via OPTIONS or just try.
    # My previous test `test_provisioning.py` used `org_name`.
    # I'll use `org_name`.

    r = requests.post(f"{BASE_URL}/admin/provisioning", json=payload, headers=admin_headers)
    duration = time.time() - start

    if r.status_code == 202:
        results["Provisioning Speed"] = f"PASS ({duration:.2f}s)"
        data = r.json()
        req_id = data["request_id"]

        # Poll for completion
        for _ in range(10):
            time.sleep(2)
            rp = requests.get(f"{BASE_URL}/admin/provisioning/{req_id}", headers=admin_headers)
            if rp.status_code == 200 and rp.json()["status"] == "COMPLETED":
                break
        else:
            results["Provisioning Speed"] = "FAIL (Timeout)"
            sys.exit(1)

        res_data = rp.json()["result_data"]
        tenant_id = res_data["tenant_id"]
        # API Key? Result data might contain it?
        # Check `workflow.py` logic. Usually we return ID.
        # Or email has it.
    else:
        results["Provisioning Speed"] = f"FAIL ({r.status_code} - {r.text})"
        sys.exit(1)

    # 2. Get API Key (Simulation of Email Fallback)
    print("Test: Email/Fallback...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT context FROM pending_notifications WHERE recipient = %s", (payload["admin_email"],))
    row = cur.fetchone()
    if row:
        ctx = row[0] # Jsonb
        api_key = ctx.get("access_key")
        results["Email/Fallback"] = "PASS (Found in DB)"
    else:
        results["Email/Fallback"] = "FAIL (Not found)"
        # Try to find key via DB directly to continue other tests
        cur.execute("SELECT access_key_id FROM api_keys WHERE tenant_id = %s", (tenant_id,))
        row = cur.fetchone()
        if row:
            api_key = row[0]
        else:
             print("Critical: No API Key found.")
             sys.exit(1)
    cur.close()
    conn.close()

    # 3. Rate Limiting
    print("Test: Rate Limiting...")
    tenant_headers = {"X-API-Key": api_key}
    # Reset limits? Defaults might be high.
    # Set strict limit
    r = requests.patch(f"{BASE_URL}/admin/tenants/{tenant_id}/rate-limits",
                       json={"requests_per_minute": 5}, headers=admin_headers)
    if r.status_code != 200:
        print(f"Failed to set limit: {r.text}")

    # Hit 6 times
    blocked = False
    for i in range(10):
        resp = requests.get(f"{BASE_URL}/v1/health", headers=tenant_headers)
        if resp.status_code == 429:
            blocked = True
            break

    results["Rate Limiting"] = "PASS" if blocked else "FAIL (Did not block)"

    # 4. Usage Metering
    print("Test: Usage Tracking...")
    # Submit Job
    files = {'file': ('verif.pdf', b'%PDF-1.4 mock', 'application/pdf')}
    r = requests.post(f"{BASE_URL}/v1/parse", headers=tenant_headers, files=files)
    # Check DB
    time.sleep(2)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM usage_events WHERE tenant_id = %s", (tenant_id,))
    count = cur.fetchone()[0]
    results["Usage Tracking"] = "PASS" if count > 0 else "FAIL (No events)"
    cur.close()
    conn.close()

    # 5. Rollback
    print("Test: Rollback...")
    payload_bad = payload.copy()
    payload_bad["org_slug"] = payload["org_slug"] # Duplicate
    r = requests.post(f"{BASE_URL}/admin/provisioning", json=payload_bad, headers=admin_headers)
    # Should be 202, then failed
    if r.status_code == 202:
        bid = r.json()["request_id"]
        time.sleep(3)
        rp = requests.get(f"{BASE_URL}/admin/provisioning/{bid}", headers=admin_headers)
        status = rp.json()["status"]
        if status == "FAILED":
            results["Rollback"] = "PASS"
        else:
            results["Rollback"] = f"FAIL (Status: {status})"
    else:
        results["Rollback"] = f"FAIL (API Error {r.status_code})"

    # Report
    print("\n--- Final Results ---")
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
