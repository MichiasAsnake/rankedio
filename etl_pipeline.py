"""
TikTok Creator Discovery Engine - ETL Pipeline

This script discovers "Comet" creators on TikTok with high velocity growth.
It queries the TikHub API, filters results, and stores data in PostgreSQL.
"""

import os
import sys
import logging
import time
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

import requests
import psycopg2
from psycopg2 import sql, extras
from psycopg2.extensions import connection as PostgresConnection
import cv2
import numpy as np
from openai import OpenAI

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not required if environment variables are already set
    pass


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('etl_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Configuration
class Config:
    """Configuration management for the ETL pipeline"""

    # Database Configuration - Supabase Style (Connection String)
    # Use POSTGRES_URL_NON_POOLING for direct connection (better for migrations/admin tasks)
    # Use POSTGRES_URL for pooled connection (better for production app queries)
    DATABASE_URL = os.getenv('POSTGRES_URL_NON_POOLING') or os.getenv('POSTGRES_URL', '')

    # Fallback to individual parameters if connection string not provided
    DB_HOST = os.getenv('POSTGRES_HOST', os.getenv('DB_HOST', 'localhost'))
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('POSTGRES_DATABASE', os.getenv('DB_NAME', 'postgres'))
    DB_USER = os.getenv('POSTGRES_USER', os.getenv('DB_USER', 'postgres'))
    DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', os.getenv('DB_PASSWORD', ''))

    # TikHub API Configuration
    TIKHUB_API_KEY = os.getenv('TIKHUB_API_KEY', '')
    TIKHUB_BASE_URL = 'https://api.tikhub.io/api/v1/tiktok/app/v3/fetch_video_search_result'

    # Comet Filter Criteria
    MIN_FOLLOWERS = 10_000
    MAX_FOLLOWERS = 100_000
    MIN_VIDEO_VIEWS = 50_000

    # API Parameters
    PUBLISH_TIME_DAYS = 7
    SORT_TYPE = 0  # Relevance

    # Performance Options
    FETCH_PROFILE_IN_DISCOVERY = True  # If True, fetches full profile during discovery for complete stats
    ENABLE_PARALLEL_PROCESSING = False  # If False, processes trends sequentially (more stable, less CDN stress)
    ENABLE_FACE_DETECTION = False  # DISABLED: Haar Cascade too unreliable, causes false rejections

class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""

    def __init__(self):
        self.conn: Optional[PostgresConnection] = None

    def connect(self) -> PostgresConnection:
        """Establish database connection"""
        try:
            # Prefer connection string (Supabase style) if available
            if Config.DATABASE_URL:
                logger.info("Connecting to database using connection string (Supabase)")
                self.conn = psycopg2.connect(Config.DATABASE_URL)
            else:
                # Fallback to individual parameters
                logger.info("Connecting to database using individual parameters")
                self.conn = psycopg2.connect(
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    database=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD
                )
            logger.info("Database connection established successfully")
            return self.conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def upsert_creator(self, cursor, creator_data: Dict, trend_keyword: str = None, breakout_video_id: str = None) -> None:
        """
        Upsert creator data into the creators table

        Args:
            cursor: Database cursor
            creator_data: Dictionary containing creator information
            trend_keyword: The trending keyword that led to discovery (e.g., "#WinterFashion")
            breakout_video_id: The video ID that led to discovery (for "Proof" feature)
        """
        # Add trend keyword and breakout video ID to creator data
        creator_data_with_metadata = creator_data.copy()
        creator_data_with_metadata['discovered_via_trend'] = trend_keyword
        creator_data_with_metadata['breakout_video_id'] = breakout_video_id

        query = """
            INSERT INTO creators (user_id, handle, nickname, avatar_url, signature, last_updated_at, discovered_via_trend, breakout_video_id)
            VALUES (%(user_id)s, %(handle)s, %(nickname)s, %(avatar_url)s, %(signature)s, %(last_updated_at)s, %(discovered_via_trend)s, %(breakout_video_id)s)
            ON CONFLICT (user_id)
            DO UPDATE SET
                handle = EXCLUDED.handle,
                nickname = EXCLUDED.nickname,
                avatar_url = EXCLUDED.avatar_url,
                signature = EXCLUDED.signature,
                last_updated_at = EXCLUDED.last_updated_at
                -- IMPORTANT: Do NOT update discovered_via_trend or breakout_video_id - keep original discovery source
        """
        cursor.execute(query, creator_data_with_metadata)

    def get_previous_stats(self, cursor, user_id: str, target_date: date) -> Optional[Tuple[int, int, int, date]]:
        """
        Retrieve the most recent stats before target_date for growth calculation

        This method now finds the MOST RECENT stats before today, not just yesterday.
        This handles cases where the pipeline doesn't run every day.

        Args:
            cursor: Database cursor
            user_id: Creator's user ID
            target_date: The date to query (typically yesterday)

        Returns:
            Tuple of (follower_count, heart_count, video_count, recorded_date) or None
        """
        query = """
            SELECT follower_count, heart_count, video_count, recorded_date
            FROM creator_stats
            WHERE user_id = %s AND recorded_date < %s
            ORDER BY recorded_date DESC
            LIMIT 1
        """
        cursor.execute(query, (user_id, target_date))
        result = cursor.fetchone()
        return result if result else None

    def insert_creator_stats(self, cursor, stats_data: Dict) -> None:
        """
        Insert creator stats with growth calculation

        Args:
            cursor: Database cursor
            stats_data: Dictionary containing stats information
        """
        query = """
            INSERT INTO creator_stats (
                user_id,
                recorded_date,
                follower_count,
                heart_count,
                video_count,
                daily_growth_followers,
                daily_growth_percent,
                source_trend
            )
            VALUES (
                %(user_id)s,
                %(recorded_date)s,
                %(follower_count)s,
                %(heart_count)s,
                %(video_count)s,
                %(daily_growth_followers)s,
                %(daily_growth_percent)s,
                -- If source_trend is NULL (roll call), use creator's discovered_via_trend
                COALESCE(
                    %(source_trend)s,
                    (SELECT discovered_via_trend FROM creators WHERE user_id = %(user_id)s)
                )
            )
            ON CONFLICT (user_id, recorded_date)
            DO UPDATE SET
                follower_count = EXCLUDED.follower_count,
                heart_count = EXCLUDED.heart_count,
                video_count = EXCLUDED.video_count,
                daily_growth_followers = EXCLUDED.daily_growth_followers,
                daily_growth_percent = EXCLUDED.daily_growth_percent,
                -- Update trend if new trend provided, otherwise keep existing or use discovered_via_trend
                source_trend = COALESCE(EXCLUDED.source_trend, creator_stats.source_trend)
        """
        cursor.execute(query, stats_data)

    def insert_daily_trend(self, cursor, trend_keyword: str, rank: int) -> None:
        """
        Insert a daily trending keyword

        Args:
            cursor: Database cursor
            trend_keyword: The trending keyword
            rank: Position in the trending list
        """
        query = """
            INSERT INTO daily_trends (trend_keyword, discovered_at, rank)
            VALUES (%s, CURRENT_DATE, %s)
            ON CONFLICT (trend_keyword, discovered_at)
            DO UPDATE SET rank = EXCLUDED.rank
        """
        cursor.execute(query, (trend_keyword, rank))

    def insert_daily_trends_batch(self, cursor, trends_with_ranks: list) -> None:
        """
        Batch insert daily trending keywords (30-50% faster than individual inserts)

        Args:
            cursor: Database cursor
            trends_with_ranks: List of tuples [(trend_keyword, rank), ...]
        """
        if not trends_with_ranks:
            return

        query = """
            INSERT INTO daily_trends (trend_keyword, discovered_at, rank)
            VALUES (%s, CURRENT_DATE, %s)
            ON CONFLICT (trend_keyword, discovered_at)
            DO UPDATE SET rank = EXCLUDED.rank
        """
        cursor.executemany(query, trends_with_ranks)


class TikHubAPI:
    """Handles TikHub API interactions"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = Config.TIKHUB_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def search_videos(self, hashtag: str, cursor: int = 0, count: int = 20) -> Optional[Dict]:
        """
        Search for videos by hashtag using TikHub API

        Args:
            hashtag: The hashtag to search (with or without #)
            cursor: Pagination cursor
            count: Number of results to fetch

        Returns:
            API response as dictionary or None if request fails
        """
        # Clean hashtag (remove # if present)
        clean_hashtag = hashtag.lstrip('#')

        params = {
            'keyword': clean_hashtag,
            'publish_time': Config.PUBLISH_TIME_DAYS,
            'sort_type': Config.SORT_TYPE,
            'cursor': cursor,
            'count': count
        }

        try:
            logger.info(f"Searching videos for hashtag: {hashtag}")
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Defensive check for valid response structure
            if not isinstance(data, dict):
                logger.warning(f"Invalid response format for {hashtag}")
                return None

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {hashtag}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON response for {hashtag}: {e}")
            return None

    def fetch_user_profile(self, handle: str) -> Optional[Dict]:
        """
        Fetch user profile by handle/unique_id using handler_user_profile endpoint

        Args:
            handle: TikTok username (unique_id)

        Returns:
            User profile data with structure: response['data']['user'][...]
        """
        profile_url = 'https://api.tikhub.io/api/v1/tiktok/app/v3/handler_user_profile'

        params = {
            'unique_id': handle
        }

        try:
            logger.debug(f"Fetching profile for @{handle}")
            response = self.session.get(profile_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Check for API-level errors
            if isinstance(data, dict):
                if data.get('code') != 200:
                    logger.warning(f"API returned non-200 code for @{handle}: {data.get('code')}")
                    return None

            return data

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch profile for @{handle}: {e}")
            return None
        except ValueError as e:
            logger.warning(f"Failed to parse profile response for @{handle}: {e}")
            return None

    def get_trending_keywords(self, limit: int = 10, region: str = 'US') -> List[str]:
        """
        Fetch trending search words from TikTok

        Args:
            limit: Number of trending keywords to return (default: 10)
            region: Region code for trending keywords (default: 'US')

        Returns:
            List of trending keyword strings
        """
        trending_url = 'https://api.tikhub.io/api/v1/tiktok/web/fetch_trending_searchwords'

        params = {
            'region': region,
            'count': str(limit)
        }

        try:
            logger.info(f"Fetching top {limit} trends from TikHub (region: {region})...")
            response = self.session.get(trending_url, params=params, timeout=30)

            # Log response status
            logger.info(f"Trending API response status: {response.status_code}")

            response.raise_for_status()
            data = response.json()

            # DEBUG: Log the full response structure to understand it
            if isinstance(data, dict):
                logger.info(f"📋 Response keys: {list(data.keys())}")
            else:
                logger.info(f"📋 Response type: {type(data)}")

            # Check for API-level errors
            if isinstance(data, dict):
                if 'code' in data:
                    logger.info(f"API response code: {data['code']}")
                    if data.get('code') != 200:
                        logger.warning(f"API returned non-200 code: {data.get('code')} - {data.get('msg', 'No message')}")
                        logger.info(f"Full response: {data}")
                        return []

            # Defensive parsing - check for data structure
            if not isinstance(data, dict):
                logger.warning(f"Invalid response format from trending API. Type: {type(data)}")
                return []

            # Extract trending words from response
            # Try multiple possible response structures
            word_list = []

            # Structure 1: { "data": { "word_list": [...] } }
            if 'data' in data:
                data_obj = data['data']
                logger.info(f"📂 Found 'data' key. Type: {type(data_obj)}")

                if isinstance(data_obj, dict):
                    logger.info(f"   Data object keys: {list(data_obj.keys())}")
                    # Try common field names (including TikHub's 'trending_search_words')
                    for field_name in ['trending_search_words', 'word_list', 'trending_list', 'list', 'words', 'search_words']:
                        if field_name in data_obj:
                            word_list = data_obj[field_name]
                            logger.info(f"   ✅ Found word list in '{field_name}': {len(word_list) if isinstance(word_list, list) else type(word_list)} items")
                            break
                elif isinstance(data_obj, list):
                    word_list = data_obj
                    logger.info(f"   'data' is a list with {len(word_list)} items")

            # Structure 2: { "word_list": [...] } (direct)
            elif 'word_list' in data:
                word_list = data['word_list']
                logger.debug(f"Found 'word_list' at root level: {len(word_list)} items")

            # Structure 3: Direct list
            elif isinstance(data, list):
                word_list = data
                logger.debug(f"Response is direct list: {len(word_list)} items")

            if not word_list:
                logger.warning("No word list found in response")
                logger.debug(f"Full response structure: {data}")
                return []

            # Extract 'word' field from each item
            trending_keywords = []
            for idx, item in enumerate(word_list[:limit]):
                keyword = None

                if isinstance(item, dict):
                    # Log first item structure for debugging
                    if idx == 0:
                        logger.info(f"   📄 First item keys: {list(item.keys())}")

                    # Try multiple possible field names (TikHub uses 'trendingSearchWord')
                    for field_name in ['trendingSearchWord', 'word', 'keyword', 'title', 'name', 'search_word', 'query']:
                        if field_name in item:
                            keyword = item[field_name]
                            break

                elif isinstance(item, str):
                    keyword = item

                if keyword and isinstance(keyword, str):
                    trending_keywords.append(keyword.strip())

            logger.info(f"✅ Found {len(trending_keywords)} trending keywords")
            if trending_keywords:
                logger.info(f"   Top trends: {', '.join(trending_keywords[:5])}")
            else:
                logger.warning(f"   Failed to extract keywords from {len(word_list)} items")
                if word_list and len(word_list) > 0:
                    logger.debug(f"   Sample item: {word_list[0]}")

            return trending_keywords

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP request failed for trending keywords: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"   Response status: {e.response.status_code}")
                logger.error(f"   Response body: {e.response.text[:500]}")
            return []
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Failed to parse trending keywords response: {e}")
            logger.error(f"   Response content: {response.text[:500] if 'response' in locals() else 'N/A'}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching trending keywords: {e}", exc_info=True)
            return []


def filter_trends_with_ai(trend_list: List[str]) -> List[str]:
    """
    Use OpenAI to classify trending keywords into "Participatory Formats" vs "Passive Topics"

    Keeps: Challenges, dances, skits, aesthetics, formats where users create original content
    Discards: News, sports events, celebrity drama, TV shows, movies, clips

    Args:
        trend_list: List of trending keyword strings from TikHub

    Returns:
        Filtered list containing only participatory trends

    Example:
        Input: ['Hurricane Hilary', 'Roman Empire Trend', 'Taylor Swift', 'Old Money Aesthetic']
        Output: ['Roman Empire Trend', 'Old Money Aesthetic']
    """
    if not trend_list:
        logger.warning("Empty trend list provided to AI filter")
        return []

    try:
        # Initialize OpenAI client (expects OPENAI_API_KEY in environment)
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        logger.info(f"🤖 Filtering {len(trend_list)} trends with AI classifier...")

        # Construct the classification prompt
        prompt = f"""You are a TikTok Trend Classifier. Your goal is to identify keywords that lead to "User-Generated Content" (Creators) rather than "Mass Media" (News/TV).

ANALYZE the list and return a JSON array of strings to KEEP.

### ✅ KEEP: "Creator Formats" (Where a human talks, shows, or does something)
1.  **Viral Trends:** Challenges, Dances, Skits, "Girl Math", "Roman Empire".
2.  **Visual Inspiration (Inspo):** "Thanksgiving Outfit", "Nail Ideas", "Hair Tutorial", "Fall Decor", "Levis 501 Fit". (Users showing off their style).
3.  **Routines & Hauls:** "Gym Bag Essentials", "Black Friday Haul", "What I Eat", "Morning Routine", "Unboxing".
4.  **Niche Communities:** General terms that imply a lifestyle vlog, e.g., "Truck Drivers USA", "Corporate Life", "Run Club", "Gymtok".
5.  **Specific Songs (Conditional):** ONLY if the keyword implies a trend or usage (e.g., "Song Name Dance", "Song Name Trend"). Pure song titles are risky but acceptable if they are currently viral sounds.

### ❌ DISCARD: "Passive Consumption" (Where users watch official footage)
1.  **News & Events:** "Election Results", "Hurricane Tracker", "Black Friday Deals" (Generic sales news), "Protest updates".
2.  **Sports Matches:** Specific matchups like "Barcelona Vs Alaves", "Score updates", "Player Stats".
3.  **Celebrity Gossip:** "Taylor Swift Dating", "Kanye West News". (Unless it's a parody/skit).
4.  **Official Media:** Movie titles ("Stranger Things 5"), TV Show episodes, "Release Date", "Trailer".
5.  **Generic E-Commerce:** "iPhone 17 Price", "Cheap Flights", "Coupon Codes". (These lead to ads, not creators).

### CRITICAL LOGIC:
* "Thanksgiving Outfit" = **KEEP** (It's a creator showing their outfit).
* "Black Friday Deals" = **DISCARD** (It's news/ads).
* "Girl Black Friday Haul" = **KEEP** (It's a creator showing what they bought).
* "Barcelona Vs Alaves" = **DISCARD** (It's a match).
* "Gym bag women" = **KEEP** (It's a routine/lifestyle).

Analyze this list and return ONLY the valid keywords as a JSON array:

{json.dumps(trend_list)}

Respond with ONLY a valid JSON array of strings. No markdown, no explanations."""
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast, cheap model for classification
            messages=[
                {"role": "system", "content": "You are a precise trend classifier. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,  # Deterministic output
            max_tokens=500
        )

        # Extract response content
        content = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present (e.g., ```json\n[...]\n```)
        if content.startswith('```'):
            # Remove markdown code block wrapper
            content = content.strip('`')
            # Remove language identifier if present (e.g., "json")
            if content.startswith('json'):
                content = content[4:].strip()

        # Parse JSON response
        filtered_trends = json.loads(content)

        if not isinstance(filtered_trends, list):
            logger.error(f"AI returned non-list response: {filtered_trends}")
            logger.warning("Falling back to original trend list (AI filter failed)")
            return trend_list

        # Log results
        discarded = [t for t in trend_list if t not in filtered_trends]
        logger.info(f"✅ AI Classification Complete:")
        logger.info(f"   Kept: {len(filtered_trends)} participatory trends")
        logger.info(f"   Discarded: {len(discarded)} passive topics")

        if filtered_trends:
            logger.info(f"   Participatory: {', '.join(filtered_trends)}")
        if discarded:
            logger.info(f"   Passive: {', '.join(discarded)}")

        return filtered_trends

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse AI response as JSON: {e}")
        logger.error(f"   AI Response: {content if 'content' in locals() else 'N/A'}")
        logger.warning("Falling back to original trend list (AI filter failed)")
        return trend_list

    except Exception as e:
        logger.error(f"❌ AI trend filtering failed: {e}", exc_info=True)
        logger.warning("Falling back to original trend list (AI filter failed)")
        return trend_list


class ContextFirstFilter:
    """
    Context-First Filtering System
    Goal: Only save TikTok-native creators, not multi-platform streamers or repost accounts
    """

    # Layer 1: Platform keywords (indicates multi-platform creator)
    PLATFORM_KEYWORDS = [
        'twitch', 'youtube', 'kick', 'discord', 'streaming', 'streamer',
        'ttv', 'yt', 'patreon', 'onlyfans', 'twitter', 'instagram',
        'fanpage', 'fan page', 'archive', 'clips', 'highlights', 'moments',
        'daily', 'compilation', 'best of'
    ]

    # Layer 2: Pronoun patterns (indicates repost account)
    REPOST_PRONOUNS = ['bro', 'he', 'she', 'they']

    # Layer 3: Minimum face area (2% of frame)
    MIN_FACE_AREA_RATIO = 0.02  # Just confirm human is present

    # Global rate limiter for image downloads (prevents overwhelming CDN)
    _image_download_semaphore = Semaphore(2)  # Max 2 concurrent downloads

    def __init__(self):
        """Initialize the face detection cascade and cache"""
        # Face detection result cache (URL -> passed/failed)
        # Avoids re-processing the same images
        self.face_detection_cache = {}

        try:
            # Load Haar Cascade for face detection
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)

            if self.face_cascade.empty():
                logger.error("Failed to load Haar Cascade classifier")
                self.face_cascade = None
            else:
                logger.info("✅ Face detection cascade loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize face cascade: {e}")
            self.face_cascade = None

    def layer1_platform_check(self, author: Dict) -> Tuple[bool, str]:
        """
        Layer 1: Context-First Metadata Analysis
        Reject creators who use TikTok as a funnel to other platforms

        Args:
            author: Author object from TikHub API

        Returns:
            (passed, reason) - True if passed, False if rejected with reason
        """
        nickname = (author.get('nickname') or '').lower()
        unique_id = (author.get('unique_id') or '').lower()
        signature = (author.get('signature') or '').lower()

        combined_text = f"{nickname} {unique_id} {signature}"

        # Check for multi-platform keywords
        for keyword in self.PLATFORM_KEYWORDS:
            if keyword in combined_text:
                return False, f"Multi-platform keyword '{keyword}' found (not TikTok-native)"

        return True, "Platform check passed (TikTok-native)"

    def layer2_pronoun_check(self, caption: str) -> Tuple[bool, str]:
        """
        Layer 2: Pronoun Check (Caption Logic)
        Reject captions that start with repost patterns like "Bro really said..."

        Args:
            caption: Video caption/description

        Returns:
            (passed, reason) - True if passed, False if rejected with reason
        """
        if not caption:
            # No caption is fine (many authentic creators don't use captions)
            return True, "No caption (allowed)"

        # Normalize caption
        caption_lower = caption.strip().lower()

        # Check if caption starts with repost pronouns
        for pronoun in self.REPOST_PRONOUNS:
            if caption_lower.startswith(pronoun + ' '):
                return False, f"Repost pattern detected: starts with '{pronoun}'"

        return True, "Pronoun check passed"

    def layer3_face_presence(self, cover_url: str) -> Tuple[bool, str]:
        """
        Layer 3: Face Presence Filter (Simplified with Caching)
        Just check if a human face exists (> 2% of frame)
        Filters out: landscape scenery, gameplay-only, text-only memes

        Args:
            cover_url: URL to video cover image

        Returns:
            (passed, reason) - True if passed, False if rejected with reason
        """
        # Skip face detection if disabled in config
        if not Config.ENABLE_FACE_DETECTION:
            return True, "Face detection disabled in config"

        # Check cache first (avoid re-processing same images)
        if cover_url in self.face_detection_cache:
            cached_result = self.face_detection_cache[cover_url]
            logger.debug(f"Face detection cache hit for {cover_url[:50]}...")
            return cached_result

        if not self.face_cascade:
            logger.warning("Face cascade not loaded, skipping face filter")
            result = (True, "Face filter skipped (cascade unavailable)")
            self.face_detection_cache[cover_url] = result
            return result

        try:
            # Use semaphore to limit concurrent downloads (prevent CDN overwhelming)
            with self._image_download_semaphore:
                # Small delay to avoid hammering CDN
                time.sleep(0.2)

                # Download cover image with retry logic (handles TikTok CDN rate limiting)
                max_retries = 2  # Reduced from 3 to speed up failures
                retry_delay = 0.5  # Start with 0.5 second

                for attempt in range(max_retries):
                    try:
                        response = requests.get(cover_url, timeout=15)  # Reduced from 30s to 15s
                        response.raise_for_status()
                        break  # Success, exit retry loop
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Image download timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            # Final attempt failed - log and re-raise
                            logger.warning(f"Image download failed after {max_retries} attempts: {str(e)[:100]}")
                            raise

            # Convert to numpy array
            image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            if frame is None:
                result = (False, "Failed to decode image")
                self.face_detection_cache[cover_url] = result
                return result

            # Resize image for faster processing (max width 640px)
            height, width = frame.shape[:2]
            max_width = 640
            if width > max_width:
                scale = max_width / width
                new_width = max_width
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
                height, width = new_height, new_width

            total_area = height * width

            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces (more lenient detection)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,  # More sensitive
                minNeighbors=3,    # More lenient
                minSize=(20, 20)   # Smaller minimum
            )

            if len(faces) == 0:
                result = (False, "No face detected (likely scenery/gameplay/text-only)")
                self.face_detection_cache[cover_url] = result
                return result

            # Get the largest face
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            _, _, w, h = largest_face  # x, y not needed (no centering check)

            # Check: Face area > 2% (just confirm human is present)
            face_area = w * h
            face_ratio = face_area / total_area

            if face_ratio < self.MIN_FACE_AREA_RATIO:
                result = (False, f"Face too small: {face_ratio:.2%} < {self.MIN_FACE_AREA_RATIO:.0%}")
                self.face_detection_cache[cover_url] = result
                return result

            result = (True, f"Face detected ({face_ratio:.2%} of frame)")
            self.face_detection_cache[cover_url] = result
            return result

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download cover image: {e}")
            result = (False, f"Image download failed: {e}")
            self.face_detection_cache[cover_url] = result
            return result
        except Exception as e:
            logger.warning(f"Face filter error: {e}")
            result = (False, f"Face filter error: {e}")
            self.face_detection_cache[cover_url] = result
            return result

    def filter_creator(self, author: Dict, caption: str, cover_url: str) -> Tuple[bool, str]:
        """
        Apply all filter layers sequentially

        Args:
            author: Author data from API
            caption: Video caption/description
            cover_url: Video cover URL

        Returns:
            (passed, reason) - True if creator passed all filters
        """
        # Layer 1: Platform check
        passed_layer1, reason1 = self.layer1_platform_check(author)
        if not passed_layer1:
            return False, f"❌ Layer 1: {reason1}"

        # Layer 2: Pronoun check
        passed_layer2, reason2 = self.layer2_pronoun_check(caption)
        if not passed_layer2:
            return False, f"❌ Layer 2: {reason2}"

        # Layer 3: Face presence
        passed_layer3, reason3 = self.layer3_face_presence(cover_url)
        if not passed_layer3:
            return False, f"❌ Layer 3: {reason3}"

        return True, f"✅ All filters passed"


class CometDiscoveryEngine:
    """Main ETL engine for discovering Comet creators"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.api = TikHubAPI(Config.TIKHUB_API_KEY)
        self.context_filter = ContextFirstFilter()  # Context-first filter
        self.discovered_creators = set()  # Track unique creators per run

        # Filter statistics
        self.filter_stats = {
            'total_processed': 0,
            'rejected_layer1': 0,
            'rejected_layer2': 0,
            'rejected_layer3': 0,
            'passed_filters': 0,
            'rejected_comet_criteria': 0,
            'saved_to_db': 0
        }

    def is_comet_creator(self, author_stats: Dict, video_stats: Dict) -> bool:
        """
        Determine if a creator qualifies as a "Comet"

        Args:
            author_stats: Creator/author statistics
            video_stats: Video statistics

        Returns:
            True if creator meets Comet criteria
        """
        try:
            follower_count = int(author_stats.get('follower_count', 0))
            play_count = int(video_stats.get('play_count', 0))

            is_comet = (
                Config.MIN_FOLLOWERS < follower_count < Config.MAX_FOLLOWERS and
                play_count > Config.MIN_VIDEO_VIEWS
            )

            return is_comet

        except (ValueError, TypeError) as e:
            logger.warning(f"Error evaluating Comet criteria: {e}")
            return False

    def extract_creator_data(self, author: Dict) -> Dict:
        """
        Extract and structure creator data from API response

        Args:
            author: Author object from API response

        Returns:
            Structured creator data dictionary
        """
        return {
            'user_id': author.get('sec_uid') or author.get('uid', ''),
            'handle': author.get('unique_id', ''),
            'nickname': author.get('nickname', ''),
            'avatar_url': author.get('avatar_thumb', {}).get('url_list', [''])[0] if author.get('avatar_thumb') else '',
            'signature': author.get('signature', ''),
            'last_updated_at': datetime.now()
        }

    def extract_stats_data(self, user_id: str, author: Dict, cursor, source_trend: str = None) -> Dict:
        """
        Extract stats data and calculate growth metrics

        Args:
            user_id: Creator's user ID
            author: Author object from API response
            cursor: Database cursor for querying previous stats
            source_trend: The trending keyword that led to this discovery

        Returns:
            Structured stats data dictionary with growth calculations
        """
        # Extract stats with multiple fallbacks (handle None, empty strings, missing keys)
        try:
            follower_count_raw = author.get('follower_count') or author.get('mplatform_followers_count') or 0
            current_follower_count = int(follower_count_raw) if follower_count_raw else 0
        except (ValueError, TypeError):
            current_follower_count = 0

        try:
            # Try multiple possible field names for total likes/hearts
            heart_count_raw = (
                author.get('total_favorited') or
                author.get('favoriting_count') or
                author.get('heart_count') or
                author.get('digg_count') or
                author.get('favorited_count') or
                0
            )
            current_heart_count = int(heart_count_raw) if heart_count_raw else 0
        except (ValueError, TypeError):
            current_heart_count = 0

        try:
            video_count_raw = author.get('aweme_count') or author.get('video_count') or 0
            current_video_count = int(video_count_raw) if video_count_raw else 0
        except (ValueError, TypeError):
            current_video_count = 0

        today = date.today()

        # Query most recent stats before today (handles gaps in daily runs)
        previous_stats = self.db_manager.get_previous_stats(cursor, user_id, today)

        # Calculate growth
        if previous_stats:
            previous_followers, _previous_hearts, _previous_videos, previous_date = previous_stats
            daily_growth = current_follower_count - previous_followers

            # Calculate days since last stats (for accurate daily rate)
            days_diff = (today - previous_date).days
            if days_diff == 0:
                days_diff = 1  # Prevent division by zero

            # Calculate average daily growth if multiple days have passed
            avg_daily_growth = daily_growth / days_diff if days_diff > 0 else daily_growth

            # Calculate percentage growth (avoid division by zero)
            if previous_followers > 0:
                growth_percent = Decimal((avg_daily_growth / previous_followers) * 100).quantize(Decimal('0.01'))
            else:
                growth_percent = Decimal('0.00')

            # Use average daily growth for display
            daily_growth = int(avg_daily_growth)
        else:
            daily_growth = 0
            growth_percent = Decimal('0.00')

        return {
            'user_id': user_id,
            'recorded_date': today,
            'follower_count': current_follower_count,
            'heart_count': current_heart_count,
            'video_count': current_video_count,
            'daily_growth_followers': daily_growth,
            'daily_growth_percent': growth_percent,
            'source_trend': source_trend
        }

    def process_video_item(self, item: Dict, cursor, source_trend: str = None) -> bool:
        """
        Process a single video item from API response with Context-First Filter

        Args:
            item: Video item from API response
            cursor: Database cursor
            source_trend: The trending keyword that led to this discovery

        Returns:
            True if creator was processed, False otherwise
        """
        try:
            self.filter_stats['total_processed'] += 1

            # Extract nested objects defensively
            aweme_info = item.get('aweme_info', {})
            if not aweme_info:
                return False

            author = aweme_info.get('author', {})
            statistics = aweme_info.get('statistics', {})
            video = aweme_info.get('video', {})

            # Extract video ID for breakout video tracking (for "Proof" feature)
            # Try multiple possible field paths with fallback, convert to string
            video_id_raw = aweme_info.get('aweme_id') or item.get('item_id') or item.get('aweme_id')
            video_id = str(video_id_raw) if video_id_raw else ''

            if not author or not statistics:
                return False

            # Extract caption (desc field)
            caption = aweme_info.get('desc', '') or ''

            # Extract cover URL from video
            cover_url = ''
            if video:
                cover = video.get('cover', {})
                if cover:
                    url_list = cover.get('url_list', [])
                    if url_list and len(url_list) > 0:
                        cover_url = url_list[0]

            # If no cover URL found, try other sources
            if not cover_url:
                # Try dynamic_cover or origin_cover as fallback
                dynamic_cover = video.get('dynamic_cover', {})
                if dynamic_cover:
                    url_list = dynamic_cover.get('url_list', [])
                    if url_list:
                        cover_url = url_list[0]

            # === CONTEXT-FIRST FILTER (BEFORE Comet check) ===
            if not cover_url:
                # No cover URL - skip this video (can't validate face)
                logger.debug("No cover URL found, skipping video")
                self.filter_stats['rejected_layer3'] += 1
                return False

            # Apply all filter layers
            passed_filter, filter_reason = self.context_filter.filter_creator(author, caption, cover_url)

            if not passed_filter:
                # Track which layer rejected this creator
                if "Layer 1" in filter_reason:
                    self.filter_stats['rejected_layer1'] += 1
                elif "Layer 2" in filter_reason:
                    self.filter_stats['rejected_layer2'] += 1
                elif "Layer 3" in filter_reason:
                    self.filter_stats['rejected_layer3'] += 1

                logger.debug(f"Filtered out: {filter_reason}")
                return False

            self.filter_stats['passed_filters'] += 1

            # Check if this is a Comet creator
            if not self.is_comet_creator(author, statistics):
                self.filter_stats['rejected_comet_criteria'] += 1
                return False

            # Extract creator data
            creator_data = self.extract_creator_data(author)
            user_id = creator_data['user_id']

            if not user_id:
                logger.warning("Skipping creator with missing user_id")
                return False

            # Username blacklist: Filter out repost/compilation accounts
            handle = creator_data['handle'].lower()
            username_blacklist = ['video', 'videos', 'clip', 'clips', 'rate', 'rating']
            if any(keyword in handle for keyword in username_blacklist):
                logger.debug(f"Rejected @{creator_data['handle']}: username contains blacklisted keyword")
                self.filter_stats['rejected_layer1'] += 1  # Count as platform filter rejection
                return False

            # Skip if already processed in this run
            if user_id in self.discovered_creators:
                return False

            # === LAYER 4: Storage & Velocity ===
            # Use savepoint for per-item transaction isolation
            cursor.execute("SAVEPOINT before_insert")

            try:
                # Upsert creator (with trend keyword and breakout video ID for discovery tracking)
                self.db_manager.upsert_creator(cursor, creator_data, trend_keyword=source_trend, breakout_video_id=video_id)

                # Conditionally fetch full user profile based on config
                # If disabled, Roll Call will populate complete stats (saves API calls)
                if Config.FETCH_PROFILE_IN_DISCOVERY:
                    handle = creator_data['handle']
                    logger.debug(f"Fetching full profile for @{handle} to get complete stats...")
                    profile_response = self.api.fetch_user_profile(handle)

                    if profile_response:
                        user_profile = profile_response.get('data', {}).get('user', {})
                        if user_profile:
                            # Use full profile data instead of video search author
                            author = user_profile
                            logger.debug(f"Using full profile data for @{handle}")
                        else:
                            logger.warning(f"No user profile data for @{handle}, using video search author")
                    else:
                        logger.warning(f"Failed to fetch profile for @{handle}, using video search author")

                    # Rate limit delay only if we made an API call
                    time.sleep(0.5)

                # Extract and insert stats with growth calculation (velocity)
                stats_data = self.extract_stats_data(user_id, author, cursor, source_trend)
                self.db_manager.insert_creator_stats(cursor, stats_data)

                # Release savepoint on success
                cursor.execute("RELEASE SAVEPOINT before_insert")

                # Mark as processed
                self.discovered_creators.add(user_id)
                self.filter_stats['saved_to_db'] += 1

                logger.info(
                    f"✅ Comet saved: @{creator_data['handle']} "
                    f"({stats_data['follower_count']:,} followers, "
                    f"growth: {stats_data['daily_growth_followers']:+,} / {stats_data['daily_growth_percent']}%)"
                )

                return True

            except psycopg2.Error as db_error:
                # Rollback to savepoint on database error
                cursor.execute("ROLLBACK TO SAVEPOINT before_insert")
                logger.warning(f"Database error for @{creator_data.get('handle', 'unknown')}: {db_error}")
                return False

        except Exception as e:
            logger.error(f"Error processing video item: {e}", exc_info=True)
            return False

    def roll_call_update(self, cursor) -> int:
        """
        "Roll Call" - Update stats for all existing creators in the database

        This ensures that even creators not found in today's trending searches
        still get their daily stats updated.

        Args:
            cursor: Database cursor

        Returns:
            Number of creators successfully updated
        """
        logger.info("\n" + "=" * 60)
        logger.info("🎯 Starting Roll Call - Updating All Roster Creators")
        logger.info("=" * 60)

        # Fetch all creators from database
        query = "SELECT user_id, handle FROM creators ORDER BY handle"
        cursor.execute(query)
        roster = cursor.fetchall()

        if not roster:
            logger.info("No creators in roster to update")
            return 0

        logger.info(f"📋 Found {len(roster)} creators in roster")

        updated_count = 0
        failed_count = 0

        for idx, (user_id, handle) in enumerate(roster, 1):
            try:
                # Skip if already processed in this run (from trending search)
                if user_id in self.discovered_creators:
                    logger.debug(f"[{idx}/{len(roster)}] Skipping @{handle} (already updated from trending)")
                    continue

                logger.info(f"[{idx}/{len(roster)}] Fetching profile for @{handle}...")

                # Fetch user profile from TikHub
                response = self.api.fetch_user_profile(handle)

                if not response:
                    logger.warning(f"Failed to fetch profile for @{handle}")
                    failed_count += 1
                    time.sleep(1)  # Rate limit protection
                    continue

                # Extract user data from response using EXACT paths
                # Path: response['data']['user'][...]
                data = response.get('data', {})
                if not data:
                    logger.warning(f"No data in response for @{handle}")
                    failed_count += 1
                    time.sleep(1)
                    continue

                user_info = data.get('user', {})
                if not user_info:
                    logger.warning(f"No user object found for @{handle}")
                    failed_count += 1
                    time.sleep(1)
                    continue

                # Extract stats using EXACT field names from handler_user_profile
                # Hearts: response['data']['user']['total_favorited']
                # Followers: response['data']['user']['follower_count']
                # Video Count: response['data']['user']['aweme_count']
                stats_data = self.extract_stats_data(user_id, user_info, cursor, source_trend=None)

                # Insert stats (will be upserted if today's record exists)
                self.db_manager.insert_creator_stats(cursor, stats_data)

                updated_count += 1
                logger.info(
                    f"  ✅ Updated: {stats_data['follower_count']:,} followers "
                    f"({stats_data['daily_growth_followers']:+,} / {stats_data['daily_growth_percent']}%)"
                )

                # Rate limit protection - sleep between requests
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error updating @{handle}: {e}", exc_info=True)
                failed_count += 1
                time.sleep(1)

        logger.info("=" * 60)
        logger.info(f"🎯 Roll Call Complete:")
        logger.info(f"   ✅ Updated: {updated_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        logger.info(f"   ⏭️  Skipped (already updated): {len(roster) - updated_count - failed_count}")
        logger.info("=" * 60)

        return updated_count

    def process_trend(self, trend_keyword: str, cursor) -> int:
        """
        Process all videos for a given trending keyword

        Args:
            trend_keyword: The trending keyword to search
            cursor: Database cursor

        Returns:
            Number of Comet creators discovered
        """
        logger.info(f"Processing trend: {trend_keyword}")

        discovered_count = 0
        api_cursor = 0
        max_pages = 5  # Limit pagination to avoid rate limits

        for page in range(max_pages):
            response = self.api.search_videos(trend_keyword, cursor=api_cursor)

            if not response:
                logger.warning(f"No response for {trend_keyword} (page {page + 1})")
                break

            # Defensive extraction of search_item_list (TikHub's field name)
            data = response.get('data', {})
            search_item_list = data.get('search_item_list', [])

            if not search_item_list:
                # Log first page response structure for debugging
                if page == 0:
                    logger.info(f"   No search_item_list found. Data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                logger.info(f"No more items for {trend_keyword}")
                break

            # Process each video item with source trend
            for item in search_item_list:
                if self.process_video_item(item, cursor, source_trend=trend_keyword):
                    discovered_count += 1

            # Check for more pages
            has_more = data.get('has_more', False)
            if not has_more:
                break

            api_cursor = data.get('cursor', 0)
            logger.info(f"Processed page {page + 1} for {trend_keyword}")

        return discovered_count

    def process_trend_parallel(self, trend_keyword: str) -> Tuple[str, int]:
        """
        Process a trend with its own database connection (for parallel execution)

        Args:
            trend_keyword: The trending keyword to search

        Returns:
            Tuple of (trend_keyword, discovered_count)
        """
        try:
            # Create dedicated database connection for this thread
            conn = self.db_manager.connect()
            cursor = conn.cursor()

            discovered_count = self.process_trend(trend_keyword, cursor)

            # Commit this trend's discoveries
            conn.commit()
            cursor.close()
            conn.close()

            return (trend_keyword, discovered_count)

        except Exception as e:
            logger.error(f"Error processing trend '{trend_keyword}' in parallel: {e}", exc_info=True)
            return (trend_keyword, 0)

    def run(self) -> None:
        """
        Main execution method for the ETL pipeline (Two-Phase System)

        Phase 1 (Discovery): Search using dynamic trending keywords
        Phase 2 (Roll Call): Update all existing creators in database

        Workflow:
        1. Fetch today's trending keywords from TikHub
        2. Search videos for each keyword (apply Context-First filters)
        3. Discover and store new Comet creators
        4. Roll call - update all existing creators' stats using handler_user_profile
        """
        logger.info("=" * 60)
        logger.info("TikTok Comet Discovery ETL Pipeline")
        logger.info("Two-Phase System: Discovery + Roll Call")
        logger.info("=" * 60)

        if not Config.TIKHUB_API_KEY:
            logger.error("TIKHUB_API_KEY not set. Please configure environment variables.")
            sys.exit(1)

        total_discovered = 0

        try:
            # Connect to database
            conn = self.db_manager.connect()
            cursor = conn.cursor()

            # ===== PHASE 1: DISCOVERY =====
            logger.info("\n" + "=" * 60)
            logger.info("PHASE 1: DISCOVERY (Trending Keywords Only)")
            logger.info("=" * 60)

            # Step 1: Fetch trending keywords (target: 10 participatory trends)
            logger.info("\n🔍 Fetching trending keywords...")

            # Fetch 30 raw trends to ensure we get 10 participatory after filtering
            # (Reduced from 100 to minimize API overhead)
            raw_trending_keywords = self.api.get_trending_keywords(limit=100)

            if not raw_trending_keywords:
                logger.error("❌ Failed to fetch trending keywords from TikHub API")
                logger.error("   Please check:")
                logger.error("   1. Your API key is valid")
                logger.error("   2. The trending API endpoint is accessible")
                logger.error("   3. Your API has sufficient credits")
                logger.info("   Pipeline will exit.")
                return

            logger.info(f"   Fetched {len(raw_trending_keywords)} raw trends from TikHub")

            # Blacklist: Filter out unwanted trends (basic string matching)
            trend_blacklist = ['2025', 'stranger things', 'bitcoin', 'gameplay', 'pepsi']
            after_blacklist = []

            for keyword in raw_trending_keywords:
                if not any(blacklisted in keyword.lower() for blacklisted in trend_blacklist):
                    after_blacklist.append(keyword)

            blacklisted_count = len(raw_trending_keywords) - len(after_blacklist)
            if blacklisted_count > 0:
                logger.info(f"   🚫 Blacklist removed {blacklisted_count} trends")

            if not after_blacklist:
                logger.error("❌ All trending keywords were blacklisted. No trends to process.")
                logger.info("   Pipeline will exit.")
                return

            # AI Filter: Use LLM to classify Participatory vs Passive trends
            all_participatory_trends = filter_trends_with_ai(after_blacklist)

            if not all_participatory_trends:
                logger.error("❌ AI filter rejected all trends as passive topics. No trends to process.")
                logger.info("   Pipeline will exit.")
                return

            # Limit to top 10 participatory trends (TikHub returns them in trending order)
            trending_keywords = all_participatory_trends[:10]

            logger.info(f"\n✅ Final selection: {len(trending_keywords)} participatory trends")
            logger.info(f"   Processing: {', '.join(trending_keywords)}\n")

            # Step 2: Store trending keywords in database (batch insert for efficiency)
            try:
                trends_with_ranks = [(keyword, rank) for rank, keyword in enumerate(trending_keywords, start=1)]
                self.db_manager.insert_daily_trends_batch(cursor, trends_with_ranks)
                logger.debug(f"Batch inserted {len(trends_with_ranks)} trends")
            except Exception as e:
                logger.warning(f"Failed to batch store trends: {e}")

            conn.commit()

            # Step 3: Process trending keywords (parallel or sequential based on config)
            if Config.ENABLE_PARALLEL_PROCESSING:
                logger.info(f"🚀 Processing {len(trending_keywords)} trends in parallel (max 2 concurrent)...")

                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit all trend processing tasks
                    future_to_trend = {
                        executor.submit(self.process_trend_parallel, keyword): keyword
                        for keyword in trending_keywords
                    }

                    # Collect results as they complete
                    for future in as_completed(future_to_trend):
                        keyword = future_to_trend[future]
                        try:
                            trend_keyword, count = future.result()
                            total_discovered += count
                            logger.info(f"✅ Discovered {count} Comets for trend: {trend_keyword}")
                        except Exception as e:
                            logger.error(f"❌ Exception processing trend '{keyword}': {e}", exc_info=True)

                logger.info(f"\n🎯 Parallel processing complete: {total_discovered} total Comets discovered\n")
            else:
                # Sequential processing (original stable method)
                logger.info(f"📋 Processing {len(trending_keywords)} trends sequentially...")

                for keyword in trending_keywords:
                    try:
                        count = self.process_trend(keyword, cursor)
                        total_discovered += count
                        logger.info(f"✅ Discovered {count} Comets for trend: {keyword}\n")

                        # Commit after each trend
                        conn.commit()

                    except Exception as e:
                        logger.error(f"❌ Error processing trend '{keyword}': {e}", exc_info=True)
                        conn.rollback()

                logger.info(f"\n🎯 Sequential processing complete: {total_discovered} total Comets discovered\n")

            # ===== PHASE 2: ROLL CALL =====
            logger.info("\n" + "=" * 60)
            logger.info("PHASE 2: ROLL CALL (Update Existing Roster)")
            logger.info("=" * 60)

            try:
                roll_call_count = self.roll_call_update(cursor)
                conn.commit()
            except Exception as e:
                logger.error(f"❌ Error during roll call update: {e}", exc_info=True)
                conn.rollback()
                roll_call_count = 0

            # ===== FINAL SUMMARY =====
            logger.info("\n" + "=" * 60)
            logger.info("🎯 PIPELINE COMPLETED")
            logger.info("=" * 60)
            logger.info(f"   Phase 1 - New Comets discovered: {total_discovered}")
            logger.info(f"   Phase 2 - Roster creators updated: {roll_call_count}")
            logger.info(f"   Total database updates: {total_discovered + roll_call_count}")
            logger.info("=" * 60)
            logger.info("\n📊 Context-First Filter Statistics:")
            logger.info(f"   Total videos processed: {self.filter_stats['total_processed']}")
            logger.info(f"   ❌ Rejected by Layer 1 (Platform Check): {self.filter_stats['rejected_layer1']}")
            logger.info(f"   ❌ Rejected by Layer 2 (Pronoun Check): {self.filter_stats['rejected_layer2']}")
            logger.info(f"   ❌ Rejected by Layer 3 (Face Presence): {self.filter_stats['rejected_layer3']}")
            logger.info(f"   ✅ Passed all filters: {self.filter_stats['passed_filters']}")
            logger.info(f"   ⚠️  Rejected by Comet criteria: {self.filter_stats['rejected_comet_criteria']}")
            logger.info(f"   💾 Saved to database: {self.filter_stats['saved_to_db']}")

            # Calculate filter efficiency
            if self.filter_stats['total_processed'] > 0:
                layer1_rate = (self.filter_stats['rejected_layer1'] / self.filter_stats['total_processed']) * 100
                layer2_rate = (self.filter_stats['rejected_layer2'] / self.filter_stats['total_processed']) * 100
                layer3_rate = (self.filter_stats['rejected_layer3'] / self.filter_stats['total_processed']) * 100
                pass_rate = (self.filter_stats['passed_filters'] / self.filter_stats['total_processed']) * 100
                logger.info(f"\n   Layer 1 (Platform) rejection rate: {layer1_rate:.1f}%")
                logger.info(f"   Layer 2 (Pronoun) rejection rate: {layer2_rate:.1f}%")
                logger.info(f"   Layer 3 (Face) rejection rate: {layer3_rate:.1f}%")
                logger.info(f"   Filter pass rate: {pass_rate:.1f}%")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Fatal error in ETL pipeline: {e}", exc_info=True)
            raise

        finally:
            if cursor:
                cursor.close()
            self.db_manager.close()


def main():
    """Main entry point for the ETL pipeline"""
    engine = CometDiscoveryEngine()
    engine.run()


if __name__ == "__main__":
    main()
