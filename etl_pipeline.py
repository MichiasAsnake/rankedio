"""
TikTok Creator Discovery Engine - ETL Pipeline

This script discovers "Comet" creators on TikTok with high velocity growth.
It queries the TikHub API, filters results, and stores data in PostgreSQL.

V2 Improvements:
- LLM Personality Filter (GPT-4o-mini vision classification)
- Trend normalization (lowercase, dedupe)
- Reduced API calls (skip Roll Call for already-updated creators)
- Faster sleeps (1s → 0.5s)
- Stale creator cleanup (14+ days no growth)
- Removed dead face detection code
"""

import os
import sys
import logging
import time
import json
import base64
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

import requests
import httpx
import psycopg2
from psycopg2 import sql, extras
from psycopg2.extensions import connection as PostgresConnection

# Try to import AI clients (optional)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
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

    # Database Configuration
    DATABASE_URL = os.getenv('POSTGRES_URL_NON_POOLING') or os.getenv('POSTGRES_URL', '')

    # Fallback to individual parameters
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
    FETCH_PROFILE_IN_DISCOVERY = True
    ENABLE_PARALLEL_PROCESSING = False
    
    # NEW: Personality Filter (uses GPT-4o-mini vision)
    ENABLE_PERSONALITY_FILTER = True
    
    # NEW: Stale creator cleanup (days without growth before removal)
    STALE_CREATOR_DAYS = 14


class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""

    def __init__(self):
        self.conn: Optional[PostgresConnection] = None

    def connect(self) -> PostgresConnection:
        """Establish database connection"""
        try:
            if Config.DATABASE_URL:
                url_parts = Config.DATABASE_URL.split('@')
                safe_url = f"***@{url_parts[-1]}" if len(url_parts) > 1 else "***"
                logger.info(f"Connecting to database: {safe_url}")
                self.conn = psycopg2.connect(Config.DATABASE_URL)
            else:
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
        """Upsert creator data into the creators table"""
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
        """
        cursor.execute(query, creator_data_with_metadata)

    def get_previous_stats(self, cursor, user_id: str, target_date: date) -> Optional[Tuple[int, int, int, date]]:
        """Retrieve the most recent stats before target_date for growth calculation"""
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
        """Insert creator stats with growth calculation"""
        query = """
            INSERT INTO creator_stats (
                user_id, recorded_date, follower_count, heart_count, video_count,
                daily_growth_followers, daily_growth_percent, source_trend
            )
            VALUES (
                %(user_id)s, %(recorded_date)s, %(follower_count)s, %(heart_count)s,
                %(video_count)s, %(daily_growth_followers)s, %(daily_growth_percent)s,
                COALESCE(%(source_trend)s, (SELECT discovered_via_trend FROM creators WHERE user_id = %(user_id)s))
            )
            ON CONFLICT (user_id, recorded_date)
            DO UPDATE SET
                follower_count = EXCLUDED.follower_count,
                heart_count = EXCLUDED.heart_count,
                video_count = EXCLUDED.video_count,
                daily_growth_followers = EXCLUDED.daily_growth_followers,
                daily_growth_percent = EXCLUDED.daily_growth_percent,
                source_trend = COALESCE(EXCLUDED.source_trend, creator_stats.source_trend)
        """
        cursor.execute(query, stats_data)

    def insert_daily_trends_batch(self, cursor, trends_with_ranks: list) -> None:
        """Batch insert daily trending keywords"""
        if not trends_with_ranks:
            return
        query = """
            INSERT INTO daily_trends (trend_keyword, discovered_at, rank)
            VALUES (%s, CURRENT_DATE, %s)
            ON CONFLICT (trend_keyword, discovered_at)
            DO UPDATE SET rank = EXCLUDED.rank
        """
        cursor.executemany(query, trends_with_ranks)

    def cleanup_stale_creators(self, cursor, days: int = 14) -> int:
        """
        Remove creators who haven't shown growth in X days
        
        Args:
            cursor: Database cursor
            days: Number of days without stats before cleanup
            
        Returns:
            Number of creators removed
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        # Find stale creators (no stats in last X days)
        cursor.execute("""
            SELECT c.user_id, c.handle
            FROM creators c
            WHERE NOT EXISTS (
                SELECT 1 FROM creator_stats cs
                WHERE cs.user_id = c.user_id
                AND cs.recorded_date >= %s
            )
        """, (cutoff_date,))
        
        stale_creators = cursor.fetchall()
        
        if not stale_creators:
            return 0
        
        stale_user_ids = [c[0] for c in stale_creators]
        stale_handles = [c[1] for c in stale_creators]
        
        logger.info(f"🧹 Found {len(stale_creators)} stale creators (no stats in {days} days)")
        logger.info(f"   Removing: {', '.join(stale_handles[:10])}{'...' if len(stale_handles) > 10 else ''}")
        
        # Delete stats first (foreign key)
        cursor.execute("""
            DELETE FROM creator_stats WHERE user_id = ANY(%s)
        """, (stale_user_ids,))
        
        # Delete creators
        cursor.execute("""
            DELETE FROM creators WHERE user_id = ANY(%s)
        """, (stale_user_ids,))
        
        return len(stale_creators)


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
        """Search for videos by hashtag using TikHub API"""
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
            return data if isinstance(data, dict) else None
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {hashtag}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON response for {hashtag}: {e}")
            return None

    def fetch_user_profile(self, handle: str) -> Optional[Dict]:
        """Fetch user profile by handle/unique_id"""
        profile_url = 'https://api.tikhub.io/api/v1/tiktok/app/v3/handler_user_profile'
        params = {'unique_id': handle}

        try:
            response = self.session.get(profile_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get('code') != 200:
                return None
            return data
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch profile for @{handle}: {e}")
            return None
        except ValueError:
            return None

    def get_trending_keywords(self, limit: int = 10, region: str = 'US') -> List[str]:
        """Fetch trending search words from TikTok"""
        trending_url = 'https://api.tikhub.io/api/v1/tiktok/web/fetch_trending_searchwords'
        params = {'region': region, 'count': str(limit)}

        try:
            logger.info(f"Fetching top {limit} trends from TikHub (region: {region})...")
            response = self.session.get(trending_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and data.get('code') != 200:
                logger.warning(f"API returned non-200 code: {data.get('code')}")
                return []

            # Extract trending words
            word_list = []
            if 'data' in data:
                data_obj = data['data']
                if isinstance(data_obj, dict):
                    for field in ['trending_search_words', 'word_list', 'trending_list']:
                        if field in data_obj:
                            word_list = data_obj[field]
                            break
                elif isinstance(data_obj, list):
                    word_list = data_obj

            trending_keywords = []
            for item in word_list[:limit]:
                keyword = None
                if isinstance(item, dict):
                    for field in ['trendingSearchWord', 'word', 'keyword', 'title']:
                        if field in item:
                            keyword = item[field]
                            break
                elif isinstance(item, str):
                    keyword = item
                if keyword:
                    trending_keywords.append(keyword.strip())

            logger.info(f"✅ Found {len(trending_keywords)} trending keywords")
            return trending_keywords

        except Exception as e:
            logger.error(f"❌ Failed to fetch trending keywords: {e}")
            return []


def normalize_trends(trend_list: List[str]) -> List[str]:
    """
    Normalize and deduplicate trends with smart grouping
    
    - Strip # prefix and whitespace
    - Normalize to lowercase for comparison
    - Remove duplicates and near-duplicates
    - Group variations (e.g., "Bad Bunny" and "Badbunny" → keep first)
    - Collapse spaces, punctuation, common suffixes
    
    Returns deduplicated list preserving original casing of first occurrence
    """
    import re
    seen = {}
    normalized = []
    
    # Common suffixes to strip for comparison
    suffixes_to_strip = [
        'trend', 'challenge', 'dance', 'song', 'sound', 'audio',
        'viral', 'tiktok', 'fyp', 'foryou', 'edit', 'version'
    ]
    
    for trend in trend_list:
        # Clean up the trend
        clean = trend.strip().lstrip('#')
        
        # Create base key: lowercase, alphanumeric only
        key = re.sub(r'[^a-z0-9]', '', clean.lower())
        
        # Also create a "core" key with common suffixes removed
        core_key = key
        for suffix in suffixes_to_strip:
            if core_key.endswith(suffix):
                core_key = core_key[:-len(suffix)]
        
        # Skip if empty
        if not key or len(key) < 3:
            continue
            
        # Check both full key and core key for duplicates
        if key not in seen and core_key not in seen:
            seen[key] = clean
            seen[core_key] = clean  # Also mark core as seen
            normalized.append(clean)
    
    logger.info(f"📋 Normalized {len(trend_list)} trends → {len(normalized)} unique")
    return normalized


def filter_trends_with_ai(trend_list: List[str]) -> List[str]:
    """
    Use OpenAI to classify trending keywords into "Participatory Formats" vs "Passive Topics"
    """
    if not trend_list:
        return []

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning("No OPENAI_API_KEY, skipping AI filter")
        return trend_list

    try:
        client = OpenAI(
            api_key=api_key,
            http_client=httpx.Client()  # Clean client without inherited proxy settings
        )
        logger.info(f"🤖 Filtering {len(trend_list)} trends with AI classifier...")

        prompt = f"""You are a TikTok Trend Classifier. Identify keywords that lead to "User-Generated Content" (Creators) rather than "Mass Media" (News/TV).

### ✅ KEEP: "Creator Formats"
- Challenges, Dances, Skits, "Girl Math", trends
- Visual Inspiration: "Outfit", "Tutorial", "Ideas"
- Routines & Hauls: "Essentials", "What I Eat", "Unboxing"
- Lifestyle: "Gymtok", "Corporate Life", "Run Club"

### ❌ DISCARD: "Passive Consumption"
- News: "Election", "Hurricane", "Price", "Deals"
- Sports: matchups, scores
- Celebrity gossip (unless parody)
- Official media: movie/TV titles, trailers
- E-commerce: "iPhone Price", "Coupon"

Return ONLY a JSON array of keywords to KEEP:

{json.dumps(trend_list)}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Respond with valid JSON array only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500
        )

        content = response.choices[0].message.content.strip()
        if content.startswith('```'):
            content = content.strip('`')
            if content.startswith('json'):
                content = content[4:].strip()

        filtered = json.loads(content)
        if not isinstance(filtered, list):
            return trend_list

        logger.info(f"✅ AI kept {len(filtered)}/{len(trend_list)} trends")
        return filtered

    except Exception as e:
        logger.error(f"❌ AI trend filtering failed: {e}")
        return trend_list


def classify_personality_with_ai(avatar_url: str, bio: str, handle: str, nickname: str = None) -> Tuple[bool, str]:
    """
    Use Claude Haiku or GPT-4o-mini to classify if a creator is a real personality
    
    This is the PRIMARY gatekeeper for creator quality. Be strict!
    
    Args:
        avatar_url: Creator's profile picture URL
        bio: Creator's bio/signature
        handle: Creator's username
        nickname: Creator's display name
        
    Returns:
        (is_personality, reason) - True if real creator, False if should be rejected
    """
    if not Config.ENABLE_PERSONALITY_FILTER:
        return True, "Personality filter disabled"
    
    prompt = f"""You are a TikTok creator quality filter. Analyze this account and determine if it's a REAL CREATOR worth tracking.

## ACCEPT (Real Creators):
- Individual people who appear on camera
- Personal brands, influencers, content creators
- People doing challenges, dances, skits, vlogs
- Beauty/fashion/fitness creators showing themselves
- Musicians/artists promoting their own work
- Names that look like real people (first names, nicknames)

## REJECT (Not Real Creators):
- Fan pages, stan accounts, update accounts
- News/media accounts, celebrity gossip
- Compilation/clip channels, "best of" accounts
- Brand accounts, corporate pages
- Meme repost accounts
- Usernames with: "daily", "clips", "updates", "news", "fan", "stan", "archive", "tv", "media", "official" (unless it's the actual celebrity)
- Generic usernames like "user123456"
- Tech/gadget review accounts (unless personal brand)
- Sports highlight accounts

## Account to Analyze:
- Username: @{handle}
- Display Name: {nickname if nickname else '(none)'}
- Bio: {bio if bio else '(no bio)'}

Based on ALL signals (username patterns, display name, bio content), is this a real individual creator?

Respond with ONLY: ACCEPT or REJECT"""

    # Try Anthropic first (Claude Haiku - fast & cheap)
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    if anthropic_key and ANTHROPIC_AVAILABLE:
        try:
            client = Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}]
            )
            result = response.content[0].text.strip().upper()
            
            if "ACCEPT" in result:
                return True, "Claude: Real creator"
            else:
                return False, f"Claude: Rejected (@{handle})"
        except Exception as e:
            logger.warning(f"Claude classification failed: {e}")
    
    # Fallback to OpenAI
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key and OPENAI_AVAILABLE:
        try:
            client = OpenAI(
                api_key=openai_key,
                http_client=httpx.Client()
            )
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a strict TikTok creator filter. Respond with ACCEPT or REJECT only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=10
            )
            result = response.choices[0].message.content.strip().upper()
            
            if "ACCEPT" in result:
                return True, "GPT: Real creator"
            else:
                return False, f"GPT: Rejected (@{handle})"
        except Exception as e:
            logger.warning(f"OpenAI classification failed: {e}")
    
    # No AI available - allow through
    return True, "No AI API key available"


class ContextFirstFilter:
    """
    Context-First Filtering System
    Filters out multi-platform creators and repost accounts
    """

    PLATFORM_KEYWORDS = [
        'twitch', 'youtube', 'kick', 'discord', 'streaming', 'streamer',
        'ttv', 'yt', 'patreon', 'onlyfans', 'twitter', 'instagram',
        'fanpage', 'fan page', 'archive', 'clips', 'highlights', 'moments',
        'daily', 'compilation', 'best of', 'edits', 'updates'
    ]

    REPOST_PRONOUNS = ['bro', 'he', 'she', 'they']

    def __init__(self):
        pass  # No face detection initialization needed

    def layer1_platform_check(self, author: Dict) -> Tuple[bool, str]:
        """Layer 1: Reject multi-platform creators"""
        nickname = (author.get('nickname') or '').lower()
        unique_id = (author.get('unique_id') or '').lower()
        signature = (author.get('signature') or '').lower()
        combined = f"{nickname} {unique_id} {signature}"

        for keyword in self.PLATFORM_KEYWORDS:
            if keyword in combined:
                return False, f"Multi-platform keyword '{keyword}' found"

        return True, "Platform check passed"

    def layer2_pronoun_check(self, caption: str) -> Tuple[bool, str]:
        """Layer 2: Reject repost captions"""
        if not caption:
            return True, "No caption"

        caption_lower = caption.strip().lower()
        for pronoun in self.REPOST_PRONOUNS:
            if caption_lower.startswith(pronoun + ' '):
                return False, f"Repost pattern: starts with '{pronoun}'"

        return True, "Pronoun check passed"

    def filter_creator(self, author: Dict, caption: str) -> Tuple[bool, str]:
        """Apply all filter layers"""
        passed1, reason1 = self.layer1_platform_check(author)
        if not passed1:
            return False, f"❌ Layer 1: {reason1}"

        passed2, reason2 = self.layer2_pronoun_check(caption)
        if not passed2:
            return False, f"❌ Layer 2: {reason2}"

        return True, "✅ Filters passed"


class CometDiscoveryEngine:
    """Main ETL engine for discovering Comet creators"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.api = TikHubAPI(Config.TIKHUB_API_KEY)
        self.context_filter = ContextFirstFilter()
        self.discovered_creators = set()  # Creators we've added to DB
        self.evaluated_creators = set()   # All creators we've evaluated (including rejected)

        self.filter_stats = {
            'total_processed': 0,
            'rejected_layer1': 0,
            'rejected_layer2': 0,
            'rejected_personality': 0,
            'passed_filters': 0,
            'rejected_comet_criteria': 0,
            'saved_to_db': 0
        }

    def is_comet_creator(self, author_stats: Dict, video_stats: Dict) -> bool:
        """Determine if a creator qualifies as a Comet"""
        try:
            follower_count = int(author_stats.get('follower_count', 0))
            play_count = int(video_stats.get('play_count', 0))
            return Config.MIN_FOLLOWERS < follower_count < Config.MAX_FOLLOWERS and play_count > Config.MIN_VIDEO_VIEWS
        except (ValueError, TypeError):
            return False

    def extract_creator_data(self, author: Dict) -> Dict:
        """Extract creator data from API response"""
        return {
            'user_id': author.get('sec_uid') or author.get('uid', ''),
            'handle': author.get('unique_id', ''),
            'nickname': author.get('nickname', ''),
            'avatar_url': author.get('avatar_thumb', {}).get('url_list', [''])[0] if author.get('avatar_thumb') else '',
            'signature': author.get('signature', ''),
            'last_updated_at': datetime.now()
        }

    def extract_stats_data(self, user_id: str, author: Dict, cursor, source_trend: str = None) -> Dict:
        """Extract stats data with growth calculation"""
        try:
            current_followers = int(author.get('follower_count') or author.get('mplatform_followers_count') or 0)
        except (ValueError, TypeError):
            current_followers = 0

        try:
            current_hearts = int(
                author.get('total_favorited') or author.get('heart_count') or 
                author.get('digg_count') or 0
            )
        except (ValueError, TypeError):
            current_hearts = 0

        try:
            current_videos = int(author.get('aweme_count') or author.get('video_count') or 0)
        except (ValueError, TypeError):
            current_videos = 0

        today = date.today()
        previous = self.db_manager.get_previous_stats(cursor, user_id, today)

        if previous:
            prev_followers, _, _, prev_date = previous
            days_diff = max((today - prev_date).days, 1)
            daily_growth = (current_followers - prev_followers) / days_diff
            growth_percent = Decimal((daily_growth / prev_followers * 100) if prev_followers > 0 else 0).quantize(Decimal('0.01'))
            daily_growth = int(daily_growth)
        else:
            daily_growth = 0
            growth_percent = Decimal('0.00')

        return {
            'user_id': user_id,
            'recorded_date': today,
            'follower_count': current_followers,
            'heart_count': current_hearts,
            'video_count': current_videos,
            'daily_growth_followers': daily_growth,
            'daily_growth_percent': growth_percent,
            'source_trend': source_trend
        }

    def process_video_item(self, item: Dict, cursor, source_trend: str = None) -> bool:
        """Process a single video item with filtering"""
        try:
            self.filter_stats['total_processed'] += 1

            aweme_info = item.get('aweme_info', {})
            if not aweme_info:
                return False

            author = aweme_info.get('author', {})
            statistics = aweme_info.get('statistics', {})
            if not author or not statistics:
                return False

            video_id = str(aweme_info.get('aweme_id') or item.get('aweme_id') or '')
            caption = aweme_info.get('desc', '') or ''

            # Context filter (platform + pronoun checks)
            passed, reason = self.context_filter.filter_creator(author, caption)
            if not passed:
                if "Layer 1" in reason:
                    self.filter_stats['rejected_layer1'] += 1
                else:
                    self.filter_stats['rejected_layer2'] += 1
                return False

            # Comet criteria check
            if not self.is_comet_creator(author, statistics):
                self.filter_stats['rejected_comet_criteria'] += 1
                return False

            creator_data = self.extract_creator_data(author)
            user_id = creator_data['user_id']
            if not user_id:
                return False

            # Username blacklist
            handle = creator_data['handle'].lower()
            blacklist = ['video', 'videos', 'clip', 'clips', 'rate', 'rating', 'daily', 'best', 'top']
            if any(kw in handle for kw in blacklist):
                self.filter_stats['rejected_layer1'] += 1
                return False

            # Skip if already evaluated (whether accepted or rejected)
            if user_id in self.evaluated_creators:
                return False
            
            # Mark as evaluated before AI call (prevents duplicate API calls)
            self.evaluated_creators.add(user_id)

            # PRIMARY FILTER: AI personality classification
            # This is the main gatekeeper - determines if account is a real creator
            if Config.ENABLE_PERSONALITY_FILTER:
                is_personality, reason = classify_personality_with_ai(
                    creator_data['avatar_url'],
                    creator_data['signature'],
                    creator_data['handle'],
                    creator_data['nickname']  # Include display name for better classification
                )
                if not is_personality:
                    logger.info(f"🚫 AI Rejected: @{creator_data['handle']} - {reason}")
                    self.filter_stats['rejected_personality'] += 1
                    return False
                else:
                    logger.info(f"✅ AI Accepted: @{creator_data['handle']}")

            self.filter_stats['passed_filters'] += 1

            # Save to database
            cursor.execute("SAVEPOINT before_insert")
            try:
                self.db_manager.upsert_creator(cursor, creator_data, trend_keyword=source_trend, breakout_video_id=video_id)

                if Config.FETCH_PROFILE_IN_DISCOVERY:
                    profile = self.api.fetch_user_profile(creator_data['handle'])
                    if profile:
                        user_profile = profile.get('data', {}).get('user', {})
                        if user_profile:
                            author = user_profile
                    time.sleep(0.3)  # Reduced from 0.5

                stats_data = self.extract_stats_data(user_id, author, cursor, source_trend)
                self.db_manager.insert_creator_stats(cursor, stats_data)

                cursor.execute("RELEASE SAVEPOINT before_insert")
                self.discovered_creators.add(user_id)
                self.filter_stats['saved_to_db'] += 1

                logger.info(f"✅ Comet: @{creator_data['handle']} ({stats_data['follower_count']:,} followers)")
                return True

            except psycopg2.Error as e:
                cursor.execute("ROLLBACK TO SAVEPOINT before_insert")
                logger.warning(f"DB error for @{creator_data.get('handle', '?')}: {e}")
                return False

        except Exception as e:
            logger.error(f"Error processing video: {e}", exc_info=True)
            return False

    def roll_call_update(self, cursor) -> int:
        """Update stats for all existing creators (skipping already-updated ones)"""
        logger.info("\n" + "=" * 60)
        logger.info("🎯 Roll Call - Updating Roster")
        logger.info("=" * 60)

        cursor.execute("SELECT user_id, handle FROM creators ORDER BY handle")
        roster = cursor.fetchall()

        if not roster:
            return 0

        # Count how many we'll skip (already processed in discovery)
        skip_count = sum(1 for uid, _ in roster if uid in self.discovered_creators)
        logger.info(f"📋 Roster: {len(roster)} creators ({skip_count} already updated today)")

        updated = 0
        failed = 0

        for idx, (user_id, handle) in enumerate(roster, 1):
            # Skip if already updated in discovery phase
            if user_id in self.discovered_creators:
                continue

            try:
                response = self.api.fetch_user_profile(handle)
                if not response:
                    failed += 1
                    time.sleep(0.5)
                    continue

                user_info = response.get('data', {}).get('user', {})
                if not user_info:
                    failed += 1
                    time.sleep(0.5)
                    continue

                stats_data = self.extract_stats_data(user_id, user_info, cursor)
                self.db_manager.insert_creator_stats(cursor, stats_data)

                updated += 1
                logger.info(f"[{idx}/{len(roster)}] ✅ @{handle}: {stats_data['follower_count']:,} ({stats_data['daily_growth_followers']:+,})")
                time.sleep(0.5)  # Reduced from 1.0

            except Exception as e:
                logger.error(f"Error updating @{handle}: {e}")
                failed += 1
                time.sleep(0.5)

        logger.info(f"🎯 Roll Call: ✅ {updated} updated, ❌ {failed} failed, ⏭️ {skip_count} skipped")
        return updated

    def process_trend(self, trend_keyword: str, cursor) -> int:
        """Process all videos for a trending keyword"""
        logger.info(f"Processing trend: {trend_keyword}")
        discovered = 0
        api_cursor = 0

        for page in range(10):  # Max 10 pages (200 videos per trend)
            response = self.api.search_videos(trend_keyword, cursor=api_cursor)
            if not response:
                break

            items = response.get('data', {}).get('search_item_list', [])
            if not items:
                break

            for item in items:
                if self.process_video_item(item, cursor, source_trend=trend_keyword):
                    discovered += 1

            if not response.get('data', {}).get('has_more', False):
                break
            api_cursor = response.get('data', {}).get('cursor', 0)

        return discovered

    def run(self) -> None:
        """Main execution: Discovery + Roll Call + Cleanup"""
        logger.info("=" * 60)
        logger.info("TikTok Comet Discovery ETL Pipeline v2")
        logger.info("=" * 60)

        if not Config.TIKHUB_API_KEY:
            logger.error("TIKHUB_API_KEY not set")
            sys.exit(1)

        total_discovered = 0

        try:
            conn = self.db_manager.connect()
            cursor = conn.cursor()

            # ===== PHASE 1: DISCOVERY =====
            logger.info("\n" + "=" * 60)
            logger.info("PHASE 1: DISCOVERY")
            logger.info("=" * 60)

            raw_trends = self.api.get_trending_keywords(limit=100)
            if not raw_trends:
                logger.error("❌ Failed to fetch trends")
                return

            # Normalize trends (dedupe)
            normalized = normalize_trends(raw_trends)

            # Blacklist
            # Minimal blacklist - just obvious non-content trends
            # AI personality filter handles creator quality, not trend filtering
            blacklist = [
                # Years/dates (not trends)
                '2024', '2025', '2026',
                # Price/product announcements (not participatory)
                'price', 'specs', 'release date', 'leaked', 'reveals',
                # Sports scores (not creator content)
                'highlights', 'vs ', ' vs', 'score',
                # News events (not trends)
                'breaking', 'announces', 'confirmed',
            ]
            filtered = [t for t in normalized if not any(b in t.lower() for b in blacklist)]
            logger.info(f"🚫 Blacklist removed {len(normalized) - len(filtered)} trends")
            logger.info(f"🚫 Blacklist removed {len(normalized) - len(filtered)} trends")

            # AI filter
            participatory = filter_trends_with_ai(filtered)
            if not participatory:
                logger.error("❌ AI filter rejected all trends")
                return

            # Top 10
            trends = participatory[:10]
            logger.info(f"✅ Final: {len(trends)} trends → {', '.join(trends)}")

            # Store trends
            self.db_manager.insert_daily_trends_batch(cursor, [(t, i+1) for i, t in enumerate(trends)])
            conn.commit()

            # Process each trend
            for trend in trends:
                try:
                    count = self.process_trend(trend, cursor)
                    total_discovered += count
                    conn.commit()
                except Exception as e:
                    logger.error(f"Error processing '{trend}': {e}")
                    conn.rollback()

            # ===== PHASE 2: ROLL CALL =====
            logger.info("\n" + "=" * 60)
            logger.info("PHASE 2: ROLL CALL")
            logger.info("=" * 60)

            try:
                roll_call_count = self.roll_call_update(cursor)
                conn.commit()
            except Exception as e:
                logger.error(f"Roll call error: {e}")
                conn.rollback()
                roll_call_count = 0

            # ===== PHASE 3: CLEANUP =====
            logger.info("\n" + "=" * 60)
            logger.info("PHASE 3: CLEANUP")
            logger.info("=" * 60)

            try:
                stale_count = self.db_manager.cleanup_stale_creators(cursor, Config.STALE_CREATOR_DAYS)
                if stale_count > 0:
                    logger.info(f"🧹 Removed {stale_count} stale creators")
                conn.commit()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                conn.rollback()

            # ===== SUMMARY =====
            logger.info("\n" + "=" * 60)
            logger.info("🎯 PIPELINE COMPLETE")
            logger.info("=" * 60)
            logger.info(f"   New Comets: {total_discovered}")
            logger.info(f"   Roster updated: {roll_call_count}")
            logger.info(f"   Filter stats:")
            logger.info(f"     - Processed: {self.filter_stats['total_processed']}")
            logger.info(f"     - Platform rejected: {self.filter_stats['rejected_layer1']}")
            logger.info(f"     - Pronoun rejected: {self.filter_stats['rejected_layer2']}")
            logger.info(f"     - Personality rejected: {self.filter_stats['rejected_personality']}")
            logger.info(f"     - Comet criteria rejected: {self.filter_stats['rejected_comet_criteria']}")
            logger.info(f"     - Saved: {self.filter_stats['saved_to_db']}")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise

        finally:
            try:
                if 'cursor' in dir() and cursor:
                    cursor.close()
            except:
                pass
            self.db_manager.close()


def main():
    engine = CometDiscoveryEngine()
    engine.run()


if __name__ == "__main__":
    main()
