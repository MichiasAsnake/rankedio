# Context-First Filtering System

## Overview

The **Context-First Filter** is designed to identify **TikTok-native creators** - creators who consider TikTok their main platform, not a funnel to Twitch, YouTube, or other platforms.

### Goal
Only save creators who are:
- ✅ TikTok-native (not multi-platform streamers)
- ✅ Original content creators (not repost accounts)
- ✅ Real humans on camera (not scenery/gameplay/text-only)

---

## 4-Layer Architecture

### Layer 1: Platform Check (Metadata)
**Purpose**: Reject multi-platform creators who use TikTok as a funnel

**How it works**:
- Scans creator's nickname, handle, and bio for platform keywords
- Rejects if found: `twitch`, `youtube`, `kick`, `discord`, `ttv`, `yt`, `patreon`, `streaming`, etc.

**Example rejections**:
- ❌ Bio: "Follow me on Twitch at twitch.tv/username"
- ❌ Handle: "@username_ttv"
- ❌ Bio: "YouTube: username | Discord in bio"

**Performance**: ⚡ Instant (no API calls)

---

### Layer 2: Pronoun Check (Caption Logic)
**Purpose**: Reject repost accounts that narrate other people's content

**How it works**:
- Scans video caption (description)
- Rejects if caption starts with: `Bro`, `He`, `She`, `They`

**Example rejections**:
- ❌ "Bro really said that 💀"
- ❌ "He was not ready for this"
- ❌ "She came prepared"
- ❌ "They thought they could win"

**Why this works**:
Repost accounts narrate content in 3rd person. Original creators either:
- Use 1st person ("I tried...", "Watch me...")
- No caption at all
- Hashtags/emojis only

**Performance**: ⚡ Instant (text analysis)

---

### Layer 3: Face Presence (Simplified CV)
**Purpose**: Confirm a human is on camera (not scenery/gameplay/text-only)

**How it works**:
- Downloads video cover image
- Uses OpenCV Haar Cascade to detect faces
- **Minimum face area**: 2% of frame (very lenient)

**What it accepts**:
- ✅ Street interviews
- ✅ Vlogs (any angle, any position)
- ✅ IRL streamers (even if off-center)
- ✅ Talking head videos

**What it rejects**:
- ❌ Landscape scenery (no people)
- ❌ Gameplay-only clips (no cam)
- ❌ Text-only meme videos
- ❌ Movie/TV clips without faces

**Performance**: 🐌 ~1-2s per video (downloads cover image)

**Note**: This layer is MUCH more lenient than the old system:
- **Old system**: Required 15%-60% face area, centered, no letterbox
- **New system**: Just needs ANY face > 2%

This prevents false rejections of authentic IRL creators who might be:
- Off-center (walking, vlogging)
- Far from camera (street interviews)
- Multiple people in frame (podcasts)

---

### Layer 4: Storage & Velocity
**Purpose**: Save TikTok-native Comets and calculate growth velocity

**What happens**:
1. **Comet Check**: 10k-100k followers, 50k+ views
2. **Database Upsert**: Save to `creators` and `creator_stats`
3. **Velocity Calculation**: Compare today's vs yesterday's follower count
4. **Growth Percentage**: `(today - yesterday) / yesterday * 100`

**Transaction safety**:
- Uses PostgreSQL savepoints for per-item isolation
- Database errors don't abort entire pipeline
- Robust rollback handling

---

## How It Differs from Old System

| Feature | Old System (IRL Human Filter) | New System (Context-First) |
|---------|-------------------------------|----------------------------|
| **Layer 1** | Generic blacklist (fanpage, edit, clip) | Platform keywords (twitch, youtube, kick) |
| **Layer 2** | Engagement ratio (0.5% minimum) | Pronoun check (Bro/He/She/They) |
| **Layer 3** | Complex face filter (15-60%, centered, letterbox) | Simple face presence (>2%, any position) |
| **Focus** | Eliminate clip accounts & spam | Eliminate multi-platform streamers |
| **Philosophy** | Geometric analysis | Context analysis |

---

## Code Structure

### Class: `ContextFirstFilter`
File: [etl_pipeline.py:405-583](etl_pipeline.py#L405-L583)

```python
class ContextFirstFilter:
    # Layer 1: Platform keywords
    PLATFORM_KEYWORDS = [
        'twitch', 'youtube', 'kick', 'discord', 'streaming', 'streamer',
        'ttv', 'yt', 'patreon', 'onlyfans', 'twitter', 'instagram',
        'fanpage', 'fan page', 'archive', 'clips', 'highlights', 'moments',
        'daily', 'compilation', 'best of'
    ]

    # Layer 2: Pronoun patterns
    REPOST_PRONOUNS = ['bro', 'he', 'she', 'they']

    # Layer 3: Minimum face area
    MIN_FACE_AREA_RATIO = 0.02  # 2% (very lenient)

    def layer1_platform_check(self, author) -> (bool, str)
    def layer2_pronoun_check(self, caption) -> (bool, str)
    def layer3_face_presence(self, cover_url) -> (bool, str)
    def filter_creator(self, author, caption, cover_url) -> (bool, str)
```

### Integration: `process_video_item()`
File: [etl_pipeline.py:699-823](etl_pipeline.py#L699-L823)

```python
# Extract data
author = aweme_info.get('author', {})
statistics = aweme_info.get('statistics', {})
caption = aweme_info.get('desc', '')
cover_url = video['cover']['url_list'][0]

# Apply Context-First Filter
passed, reason = self.context_filter.filter_creator(author, caption, cover_url)

if not passed:
    # Track rejection layer
    return False

# Check Comet criteria (10k-100k followers, 50k+ views)
if not self.is_comet_creator(author, statistics):
    return False

# Layer 4: Save to database with velocity calculation
save_with_growth_tracking(...)
```

---

## Filter Statistics Example

```
📊 Context-First Filter Statistics:
   Total videos processed: 1000
   ❌ Rejected by Layer 1 (Platform Check): 250
   ❌ Rejected by Layer 2 (Pronoun Check): 150
   ❌ Rejected by Layer 3 (Face Presence): 300
   ✅ Passed all filters: 300
   ⚠️  Rejected by Comet criteria: 200
   💾 Saved to database: 100

   Layer 1 (Platform) rejection rate: 25.0%
   Layer 2 (Pronoun) rejection rate: 15.0%
   Layer 3 (Face) rejection rate: 30.0%
   Filter pass rate: 30.0%
```

**Interpretation**:
- 25% are multi-platform creators (Twitch streamers, YouTubers)
- 15% are repost accounts (narrating others' content)
- 30% have no human on camera (scenery, gameplay, text)
- 30% pass all filters
- 20% pass filters but aren't Comets (wrong follower count/views)
- 10% saved to database (authentic TikTok-native Comets)

---

## Customization

### Add More Platform Keywords

```python
PLATFORM_KEYWORDS = [
    'twitch', 'youtube', 'kick',
    'rumble',  # Add custom platforms
    'substack',
    'newsletter'
]
```

### Add More Pronoun Patterns

```python
REPOST_PRONOUNS = [
    'bro', 'he', 'she', 'they',
    'dude',  # Add slang
    'man',
    'this guy'
]
```

### Adjust Face Detection Sensitivity

```python
# More lenient (accept smaller faces)
MIN_FACE_AREA_RATIO = 0.01  # 1%

# More strict (require larger faces)
MIN_FACE_AREA_RATIO = 0.05  # 5%
```

---

## What Gets Saved Now?

### ✅ Accepted (TikTok-Native Comets)
- Street interview creators (authentic IRL)
- Vloggers (TikTok as main platform)
- Original content creators
- Comedy sketches (person on camera)
- Educational content (presenter visible)

### ❌ Rejected (Multi-Platform or Repost)
- Twitch streamers (Layer 1: "twitch" in bio)
- YouTube clip channels (Layer 1: "youtube" in bio)
- Repost accounts (Layer 2: "Bro really said...")
- Gameplay-only (Layer 3: no face detected)
- Scenery videos (Layer 3: no face detected)
- Fanpage compilations (Layer 1: "fanpage" in bio)

---

## Example Workflow

```bash
# Run the pipeline
python3 etl_pipeline.py

# Output:
🔍 Fetching today's top trends...
✅ Found 10 trending keywords
   Top trends: Girl Dinner, NPC Stream, Street Interview, ...

Processing trend: Girl Dinner

# Layer 1 rejection:
Filtered out: ❌ Layer 1: Multi-platform keyword 'twitch' found (not TikTok-native)

# Layer 2 rejection:
Filtered out: ❌ Layer 2: Repost pattern detected: starts with 'bro'

# Layer 3 rejection:
Filtered out: ❌ Layer 3: No face detected (likely scenery/gameplay/text-only)

# Pass all filters + Comet criteria:
✅ Comet saved: @streetinterviewer123 (47,521 followers, growth: +2,341 / 5.18%)

# Statistics at the end:
📊 Context-First Filter Statistics:
   Total videos processed: 1000
   ❌ Rejected by Layer 1 (Platform Check): 250
   ❌ Rejected by Layer 2 (Pronoun Check): 150
   ❌ Rejected by Layer 3 (Face Presence): 300
   ✅ Passed all filters: 300
   💾 Saved to database: 100
```

---

## Database Schema

No changes required from v2.0.0 - continues to use:

```sql
-- Creators table
CREATE TABLE creators (
    user_id VARCHAR(255) PRIMARY KEY,
    handle VARCHAR(100),
    nickname VARCHAR(255),
    avatar_url TEXT,
    signature TEXT,
    last_updated_at TIMESTAMP
);

-- Creator stats with growth tracking
CREATE TABLE creator_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    recorded_date DATE,
    follower_count BIGINT,
    daily_growth_followers INT,      -- Today - Yesterday
    daily_growth_percent DECIMAL(5,2), -- Velocity %
    source_trend VARCHAR(255),        -- Which trend found them
    UNIQUE(user_id, recorded_date)
);

-- Daily trends
CREATE TABLE daily_trends (
    id SERIAL PRIMARY KEY,
    trend_keyword VARCHAR(255),
    discovered_at DATE,
    rank INT,
    UNIQUE(trend_keyword, discovered_at)
);
```

---

## Performance

| Layer | Speed | Cost | Typical Rejection Rate |
|-------|-------|------|----------------------|
| Layer 1 | ⚡ Instant | Free | 20-30% |
| Layer 2 | ⚡ Instant | Free | 10-20% |
| Layer 3 | 🐌 1-2s | Bandwidth | 30-40% |
| **Total** | ~1.5s/video | Low | **60-70%** |

**Expected Results**:
- Process 1000 videos → Save ~100-300 authentic TikTok-native Comets
- Much higher quality than old system (fewer multi-platform streamers)
- Lower false rejection rate (more lenient face detection)

---

## Troubleshooting

### High Layer 1 Rejections (>40%)

**Possible causes**:
- Trending keywords attract multi-platform creators
- You're in a gaming/streaming niche

**Solutions**:
- Adjust platform keywords (remove overly broad terms)
- Check which trends are producing rejections:
  ```sql
  SELECT source_trend, COUNT(*)
  FROM creator_stats
  GROUP BY source_trend;
  ```

---

### High Layer 2 Rejections (>30%)

**Possible causes**:
- Trending keywords attract reaction/commentary content
- Many repost accounts in that niche

**Solutions**:
- This is actually good - means the filter is working!
- Consider the trending keyword quality

---

### High Layer 3 Rejections (>50%)

**Possible causes**:
- Many scenery/gameplay videos in trending keywords
- Face detection too strict

**Solutions**:
- Lower the minimum face area:
  ```python
  MIN_FACE_AREA_RATIO = 0.01  # 1% instead of 2%
  ```
- Check OpenCV installation:
  ```bash
  python3 -c "import cv2; print(cv2.__version__)"
  ```

---

### Low Layer 2 Rejections (<5%)

**Possible causes**:
- Pronoun patterns not capturing regional slang
- Different repost patterns in your niche

**Solutions**:
- Add more pronoun patterns:
  ```python
  REPOST_PRONOUNS = ['bro', 'he', 'she', 'they', 'dude', 'man', 'this guy']
  ```
- Monitor saved creators for quality

---

## Migration from Old System

If you were using the old IRL Human Filter:

**What changed**:
1. Class renamed: `IRLHumanFilter` → `ContextFirstFilter`
2. Layer 1: Generic blacklist → Platform keywords
3. Layer 2: Engagement ratio → Pronoun check (NEW)
4. Layer 3: Complex face geometry → Simple face presence

**Breaking changes**: None (fully backward compatible)

**Action required**: None (automatically uses new filter)

---

## Next Steps

1. **Run the pipeline** and observe filter statistics
2. **Check saved creators** for quality:
   ```sql
   SELECT handle, nickname, signature, follower_count
   FROM creators
   JOIN creator_stats ON creators.user_id = creator_stats.user_id
   WHERE recorded_date = CURRENT_DATE
   ORDER BY daily_growth_percent DESC;
   ```
3. **Adjust thresholds** based on your rejection rates
4. **Monitor trends** that produce the most TikTok-native Comets

---

## Philosophy: Context > Geometry

The old system focused on **geometric analysis** (face size, position, letterboxing).

The new system focuses on **context analysis** (platform intent, content originality).

**Why?**
- Geometry can't distinguish IRL streamers from vloggers (both have faces on camera)
- Context reveals platform intent (Twitch in bio = not TikTok-native)
- Pronoun patterns reveal content originality (3rd person = repost)

**Result**: Higher precision for finding authentic TikTok-native creators.

---

## Questions?

See the main [README.md](README.md) for general usage or [QUICKSTART.md](QUICKSTART.md) for setup.
