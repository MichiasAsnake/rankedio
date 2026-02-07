import psycopg2

DATABASE_URL = "postgresql://postgres.aoirpacvupeglqpdanmo:Cheerios%40151714161930@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Get table schemas
for table in ['creators', 'creator_stats', 'daily_trends']:
    print(f"\n{'='*60}")
    print(f"TABLE: {table}")
    print('='*60)
    cursor.execute(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    for col in cursor.fetchall():
        print(f"  {col[0]:30} {col[1]:20} {'NULL' if col[2]=='YES' else 'NOT NULL'}")

# Get indexes
print(f"\n{'='*60}")
print("INDEXES")
print('='*60)
cursor.execute("""
    SELECT tablename, indexname, indexdef
    FROM pg_indexes
    WHERE schemaname = 'public'
""")
for idx in cursor.fetchall():
    print(f"  {idx[0]}: {idx[1]}")

cursor.close()
conn.close()
