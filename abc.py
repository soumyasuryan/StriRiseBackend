import psycopg2
import os
import os
from dotenv import load_dotenv

load_dotenv()
print(os.environ.get("DATABASE_URL"))






DATABASE_URL = os.environ.get("DATABASE_URL")

try:
    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )
    print("✅ Database connection successful!")

    cur = conn.cursor()
    cur.execute("SELECT version();")
    print("PostgreSQL version:", cur.fetchone())

    cur.close()
    conn.close()

except Exception as e:
    print("❌ Database connection failed")
    print(e)
