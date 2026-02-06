import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def setup():
    # Connect to default 'postgres' db
    conn = psycopg2.connect(
        host="127.0.0.1",
        port="5432",
        database="postgres",
        user="postgres",
        password="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Create User
    try:
        cur.execute("CREATE USER parsefin WITH PASSWORD 'password';")
        print("User 'parsefin' created.")
    except psycopg2.errors.DuplicateObject:
        print("User 'parsefin' already exists.")

    # Create DB
    try:
        cur.execute("CREATE DATABASE brokerage_parser OWNER parsefin;")
        print("Database 'brokerage_parser' created.")
    except psycopg2.errors.DuplicateDatabase:
        print("Database 'brokerage_parser' already exists.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    setup()
