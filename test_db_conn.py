import psycopg2
import sys

creds = [
    ("parsefin", "password"),
    ("postgres", "password"),
    ("postgres", "postgres"),
    ("postgres", "admin"),
    ("postgres", "root"),
    ("postgres", "")
]

for user, password in creds:
    try:
        print(f"Testing {user}:{password}...")
        conn = psycopg2.connect(
            host="127.0.0.1",
            port="5432",
            database="brokerage_parser",
            user=user,
            password=password
        )
        print(f"SUCCESS: Connected with {user}:{password}")
        conn.close()
        sys.exit(0)
    except Exception as e:
        print(f"Failed: {e}")

print("All attempts failed.")
sys.exit(1)
