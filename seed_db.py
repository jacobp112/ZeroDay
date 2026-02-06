import psycopg2
import uuid

def seed():
    conn = psycopg2.connect(
        host="127.0.0.1",
        port="5432",
        database="brokerage_parser",
        user="parsefin",
        password="password"
    )
    cur = conn.cursor()

    # Drop existing if any
    cur.execute("DROP TABLE IF EXISTS jobs CASCADE;")

    # Create Legacy Jobs Table (No Tenant ID)
    cur.execute("""
    CREATE TABLE jobs (
        job_id UUID PRIMARY KEY,
        client_id VARCHAR(255) NOT NULL,
        idempotency_key VARCHAR(255),
        status VARCHAR(50) NOT NULL,
        progress_percent INTEGER DEFAULT 0,
        current_step VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        expires_at TIMESTAMPTZ,
        file_s3_key VARCHAR(1024) NOT NULL,
        file_sha256 VARCHAR(64),
        result_s3_key VARCHAR(1024),
        error_code VARCHAR(50),
        error_message TEXT,
        error_trace TEXT
    );
    """)

    # Insert Dummy Data
    job_uuid = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO jobs (job_id, client_id, status, file_s3_key, created_at)
        VALUES (%s, 'legacy_client', 'PENDING', 's3://bucket/file.pdf', NOW())
    """, (job_uuid,))

    print(f"Seeded jobs table with 1 row. Job ID: {job_uuid}")

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    seed()
