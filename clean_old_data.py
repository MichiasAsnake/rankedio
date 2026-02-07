import psycopg2
from datetime import datetime

DATABASE_URL = "postgresql://postgres.aoirpacvupeglqpdanmo:Cheerios%40151714161930@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

today = '2026-02-07'

print("=== CLEANING OLD DATA ===\n")

# 1. Delete old stats (before today)
cursor.execute("DELETE FROM creator_stats WHERE recorded_date < %s", (today,))
old_stats_deleted = cursor.rowcount
print(f"✓ Deleted {old_stats_deleted} old stats (before {today})")

# 2. Delete old trends (before today)
cursor.execute("DELETE FROM daily_trends WHERE DATE(discovered_at) < %s", (today,))
old_trends_deleted = cursor.rowcount
print(f"✓ Deleted {old_trends_deleted} old trends (before {today})")

# 3. Delete orphaned creators (no stats remaining)
cursor.execute("""
    DELETE FROM creators 
    WHERE user_id NOT IN (SELECT DISTINCT user_id FROM creator_stats)
""")
orphaned_creators_deleted = cursor.rowcount
print(f"✓ Deleted {orphaned_creators_deleted} orphaned creators (no stats)")

conn.commit()

# Show final state
print("\n=== FRESH STATE ===")
cursor.execute("SELECT COUNT(*) FROM creators")
print(f"Creators: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM creator_stats")
print(f"Stats: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM daily_trends")
print(f"Trends: {cursor.fetchone()[0]}")

cursor.close()
conn.close()
print("\n✅ Database cleaned! Fresh start from today.")
