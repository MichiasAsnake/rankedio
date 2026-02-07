import psycopg2

DATABASE_URL = "postgresql://postgres.aoirpacvupeglqpdanmo:Cheerios%40151714161930@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Check creators and their source trends
cursor.execute("""
    SELECT c.handle, c.user_id, cs.source_trend, cs.recorded_date
    FROM creators c
    JOIN creator_stats cs ON c.user_id = cs.user_id
    ORDER BY cs.source_trend, c.handle
""")

print("=== CREATORS BY SOURCE TREND ===\n")
current_trend = None
for row in cursor.fetchall():
    handle, user_id, source_trend, recorded_date = row
    if source_trend != current_trend:
        current_trend = source_trend
        print(f"\n📌 Trend: {source_trend}")
    print(f"   @{handle} ({recorded_date})")

# Check what trends exist now
print("\n\n=== ACTIVE TRENDS IN daily_trends ===")
cursor.execute("SELECT trend_keyword FROM daily_trends ORDER BY trend_keyword")
for row in cursor.fetchall():
    print(f"  • {row[0]}")

cursor.close()
conn.close()
