import psycopg2

DATABASE_URL = "postgresql://postgres.aoirpacvupeglqpdanmo:Cheerios%40151714161930@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Get today's active trends
cursor.execute("SELECT trend_keyword FROM daily_trends")
active_trends = [row[0].lower() for row in cursor.fetchall()]
print(f"Active trends ({len(active_trends)}): {active_trends}\n")

# Find stats with stale source_trends
cursor.execute("""
    SELECT DISTINCT source_trend 
    FROM creator_stats 
    WHERE LOWER(source_trend) NOT IN %s
""", (tuple(active_trends),))
stale_trends = [row[0] for row in cursor.fetchall()]
print(f"Stale trends to remove ({len(stale_trends)}):")
for t in stale_trends:
    print(f"  ❌ {t}")

# Delete stats with stale source_trends
cursor.execute("""
    DELETE FROM creator_stats 
    WHERE LOWER(source_trend) NOT IN %s
""", (tuple(active_trends),))
deleted_stats = cursor.rowcount
print(f"\n✓ Deleted {deleted_stats} stats with stale trends")

# Delete orphaned creators
cursor.execute("""
    DELETE FROM creators 
    WHERE user_id NOT IN (SELECT DISTINCT user_id FROM creator_stats)
""")
deleted_creators = cursor.rowcount
print(f"✓ Deleted {deleted_creators} orphaned creators")

conn.commit()

# Final state
print("\n=== CLEAN STATE ===")
cursor.execute("SELECT COUNT(*) FROM creators")
print(f"Creators: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM creator_stats")
print(f"Stats: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM daily_trends")
print(f"Trends: {cursor.fetchone()[0]}")

cursor.close()
conn.close()
print("\n✅ Stale trends cleaned!")
