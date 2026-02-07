import os
import psycopg2
from datetime import datetime, timedelta

# Use pooler URL
DATABASE_URL = "postgresql://postgres.aoirpacvupeglqpdanmo:Cheerios%40151714161930@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Check creators count
cursor.execute("SELECT COUNT(*) FROM creators")
print(f"Total creators: {cursor.fetchone()[0]}")

# Check stats count and date range
cursor.execute("SELECT COUNT(*), MIN(recorded_date), MAX(recorded_date) FROM creator_stats")
row = cursor.fetchone()
print(f"Total stats: {row[0]}, Date range: {row[1]} to {row[2]}")

# Check stats from last 30 days
thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
cursor.execute("SELECT COUNT(*) FROM creator_stats WHERE recorded_date >= %s", (thirty_days_ago,))
print(f"Stats from last 30 days: {cursor.fetchone()[0]}")

# Check trends
cursor.execute("SELECT COUNT(*), MIN(discovered_at), MAX(discovered_at) FROM daily_trends")
row = cursor.fetchone()
print(f"Total trends: {row[0]}, Date range: {row[1]} to {row[2]}")

# Check most recent stats
cursor.execute("""
    SELECT c.handle, cs.follower_count, cs.daily_growth_percent, cs.recorded_date
    FROM creator_stats cs
    JOIN creators c ON cs.user_id = c.user_id
    ORDER BY cs.recorded_date DESC
    LIMIT 5
""")
print("\nMost recent stats:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} followers, {row[2]}% growth, {row[3]}")

cursor.close()
conn.close()
