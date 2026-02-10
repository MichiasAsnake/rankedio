#!/usr/bin/env python3
"""
Backfill Avatar Cache

One-time script to cache all existing creator avatars to Supabase Storage.
Run this once to fix existing broken avatars, then the ETL will handle new ones.
"""

import os
import sys
import logging
import psycopg2
from avatar_cache import cache_avatar, get_supabase_client, ensure_bucket_exists

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DATABASE_URL = os.getenv('POSTGRES_URL_NON_POOLING') or os.getenv('POSTGRES_URL', '')


def get_db_connection():
    """Get database connection."""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        return psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            dbname=os.getenv('POSTGRES_DATABASE', 'postgres'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )


def backfill_avatars():
    """Fetch all creators and cache their avatars."""
    # Ensure Supabase is ready
    client = get_supabase_client()
    if not client:
        logger.error("Could not connect to Supabase")
        return
    
    if not ensure_bucket_exists(client):
        logger.error("Could not ensure avatars bucket exists")
        return
    
    # Connect to database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        logger.error(f"Could not connect to database: {e}")
        return
    
    try:
        # Get all creators with non-Supabase avatars
        cursor.execute("""
            SELECT user_id, handle, avatar_url 
            FROM creators 
            WHERE avatar_url IS NOT NULL 
            AND avatar_url != ''
            AND avatar_url NOT LIKE '%supabase%'
            ORDER BY handle
        """)
        creators = cursor.fetchall()
        
        logger.info(f"Found {len(creators)} creators with uncached avatars")
        
        cached = 0
        failed = 0
        
        for user_id, handle, avatar_url in creators:
            try:
                cached_url = cache_avatar(user_id, avatar_url)
                
                if cached_url != avatar_url and 'supabase' in cached_url:
                    # Update database with cached URL
                    cursor.execute(
                        "UPDATE creators SET avatar_url = %s WHERE user_id = %s",
                        (cached_url, user_id)
                    )
                    cached += 1
                    logger.info(f"✅ Cached @{handle}")
                else:
                    failed += 1
                    logger.warning(f"⚠️ Failed @{handle}")
                    
            except Exception as e:
                failed += 1
                logger.error(f"❌ Error caching @{handle}: {e}")
        
        conn.commit()
        logger.info(f"\n{'='*50}")
        logger.info(f"Backfill complete: {cached} cached, {failed} failed")
        logger.info(f"{'='*50}")
        
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    backfill_avatars()
