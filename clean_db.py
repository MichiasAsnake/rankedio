import psycopg2
from datetime import datetime, timedelta

DATABASE_URL = "postgresql://postgres.aoirpacvupeglqpdanmo:Cheerios%40151714161930@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Check current state
print("=== CURRENT STATE ===")
cursor.execute("SELECT COUNT(*) FROM creators")
print(f"Total creators: {cursor.fetchone()[0]}")

cursor.execute("SELECT recorded_date, COUNT(*) FROM creator_stats GROUP BY recorded_date ORDER BY recorded_date")
print("\nStats by date:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} records")

cursor.execute("SELECT DATE(discovered_at), COUNT(*) FROM daily_trends GROUP BY DATE(discovered_at) ORDER BY DATE(discovered_at)")
print("\nTrends by date:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} trends")

# Find today's date
today = datetime.now().strftime('%Y-%m-%d')
print(f"\nToday: {today}")

cursor.close()
conn.close()
