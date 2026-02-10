"""
Avatar Caching Module for RankedIO

Downloads TikTok avatars and stores them in Supabase Storage
for permanent, reliable access.
"""

import os
import logging
import hashlib
import requests
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Supabase config
SUPABASE_URL = os.getenv('NEXT_PUBLIC_SUPABASE_URL', 'https://aoirpacvupeglqpdanmo.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
SUPABASE_ANON_KEY = os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')

BUCKET_NAME = 'avatars'

# Cache for already-processed avatars (in-memory for single run)
_processed_cache = set()


def get_supabase_client() -> Optional[Client]:
    """Get Supabase client with service role key for storage access."""
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if not key:
        logger.warning("No Supabase key available for avatar caching")
        return None
    try:
        return create_client(SUPABASE_URL, key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def ensure_bucket_exists(client: Client) -> bool:
    """Ensure the avatars bucket exists, create if not."""
    try:
        # Try to get bucket info
        buckets = client.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        
        if BUCKET_NAME not in bucket_names:
            # Create the bucket with public access
            client.storage.create_bucket(
                BUCKET_NAME,
                options={
                    'public': True,
                    'file_size_limit': 1024 * 1024,  # 1MB max per avatar
                    'allowed_mime_types': ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
                }
            )
            logger.info(f"Created storage bucket: {BUCKET_NAME}")
        return True
    except Exception as e:
        logger.error(f"Failed to ensure bucket exists: {e}")
        return False


def get_avatar_filename(user_id: str, original_url: str) -> str:
    """Generate a consistent filename for an avatar."""
    # Use user_id + hash of URL for uniqueness
    url_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
    return f"{user_id}_{url_hash}.jpg"


def download_avatar(url: str) -> Optional[bytes]:
    """Download avatar image from TikTok CDN."""
    if not url:
        return None
    
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Check if it's actually an image
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logger.warning(f"URL did not return an image: {url}")
            return None
            
        return response.content
    except Exception as e:
        logger.warning(f"Failed to download avatar from {url[:50]}...: {e}")
        return None


def upload_avatar(client: Client, user_id: str, image_data: bytes, original_url: str) -> Optional[str]:
    """Upload avatar to Supabase Storage and return the public URL."""
    try:
        filename = get_avatar_filename(user_id, original_url)
        file_path = f"{filename}"
        
        # Upload to storage (upsert)
        result = client.storage.from_(BUCKET_NAME).upload(
            file_path,
            image_data,
            file_options={
                'content-type': 'image/jpeg',
                'upsert': 'true'
            }
        )
        
        # Get public URL
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        logger.debug(f"Uploaded avatar for {user_id}: {public_url}")
        return public_url
        
    except Exception as e:
        logger.warning(f"Failed to upload avatar for {user_id}: {e}")
        return None


def cache_avatar(user_id: str, tiktok_avatar_url: str) -> str:
    """
    Cache a TikTok avatar to Supabase Storage.
    
    Returns:
        The cached URL (Supabase) if successful, otherwise the original TikTok URL.
    """
    if not tiktok_avatar_url:
        return ''
    
    # Skip if already processed this run
    cache_key = f"{user_id}:{tiktok_avatar_url}"
    if cache_key in _processed_cache:
        return tiktok_avatar_url  # Return original, we've already tried
    _processed_cache.add(cache_key)
    
    # Check if it's already a Supabase URL
    if 'supabase' in tiktok_avatar_url:
        return tiktok_avatar_url
    
    # Get client
    client = get_supabase_client()
    if not client:
        return tiktok_avatar_url
    
    # Ensure bucket exists
    if not ensure_bucket_exists(client):
        return tiktok_avatar_url
    
    # Download avatar
    image_data = download_avatar(tiktok_avatar_url)
    if not image_data:
        return tiktok_avatar_url
    
    # Upload to Supabase
    cached_url = upload_avatar(client, user_id, image_data, tiktok_avatar_url)
    if cached_url:
        return cached_url
    
    return tiktok_avatar_url


def cache_avatars_batch(creators: list) -> list:
    """
    Cache avatars for a batch of creators.
    
    Args:
        creators: List of dicts with 'user_id' and 'avatar_url' keys
        
    Returns:
        Same list with 'avatar_url' updated to cached URLs where successful
    """
    client = get_supabase_client()
    if not client:
        logger.warning("Supabase client not available, skipping avatar caching")
        return creators
    
    if not ensure_bucket_exists(client):
        return creators
    
    cached_count = 0
    for creator in creators:
        user_id = creator.get('user_id', '')
        original_url = creator.get('avatar_url', '')
        
        if not original_url or 'supabase' in original_url:
            continue
        
        cached_url = cache_avatar(user_id, original_url)
        if cached_url != original_url:
            creator['avatar_url'] = cached_url
            cached_count += 1
    
    if cached_count > 0:
        logger.info(f"Cached {cached_count} avatars to Supabase Storage")
    
    return creators
