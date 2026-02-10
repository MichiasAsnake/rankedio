import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export type Creator = {
  user_id: string
  handle: string
  avatar_url: string | null
  nickname: string | null
}

export type CreatorStats = {
  user_id: string
  follower_count: number
  daily_growth_percent: number
  heart_count: number
  recorded_date: string
  source_trend: string | null
}

export type TrajectoryPoint = {
  date: string
  followers: number
  growth: number
}

export type ConsistencyRating = 'A+' | 'A' | 'B' | 'C' | 'Spike'

export type RisingCreator = Creator & {
  stats: CreatorStats
  trajectory: TrajectoryPoint[]
  vibe_score: number
  consistency_score: ConsistencyRating
  growth_days: number // Number of days with positive growth in last 30
  avg_30d_growth: number
  is_hidden_gem: boolean // Low followers (<50k) but high trajectory
  rank: number
}

/**
 * Calculate consistency rating based on growth pattern
 */
function calculateConsistencyScore(
  growthDays: number,
  totalDays: number
): ConsistencyRating {
  const ratio = growthDays / totalDays
  if (ratio >= 0.9) return 'A+' // 90%+ consistent growth
  if (ratio >= 0.75) return 'A' // 75%+ steady growth
  if (ratio >= 0.5) return 'B' // 50%+ moderate growth
  if (ratio >= 0.3) return 'C' // 30%+ occasional growth
  return 'Spike' // <30% = likely viral spike
}

/**
 * Fetch top 50 rising creators with 30-day trajectory data
 * Focus: Long-term creator trajectories, not viral spikes
 * Sorted by: 30-day average growth and consistency
 */
export async function getRisingCreators(
  category?: string | null
): Promise<RisingCreator[]> {
  // Get date range (last 30 days)
  const today = new Date()
  const thirtyDaysAgo = new Date(today)
  thirtyDaysAgo.setDate(today.getDate() - 30)

  const todayStr = today.toISOString().split('T')[0]
  const thirtyDaysAgoStr = thirtyDaysAgo.toISOString().split('T')[0]

  // Fetch all stats for last 30 days
  let query = supabase
    .from('creator_stats')
    .select(
      `
      user_id,
      follower_count,
      daily_growth_percent,
      heart_count,
      recorded_date,
      source_trend,
      creators!inner (
        handle,
        avatar_url,
        nickname
      )
    `
    )
    .gte('recorded_date', thirtyDaysAgoStr)
    .lte('recorded_date', todayStr)
    .order('recorded_date', { ascending: true })

  const { data, error } = await query

  if (error) {
    console.error('Error fetching rising creators:', error)
    return []
  }

  if (!data) return []

  // Group by user_id to build trajectories
  const creatorMap = new Map<string, any>()

  data.forEach((item: any) => {
    if (!creatorMap.has(item.user_id)) {
      creatorMap.set(item.user_id, {
        user_id: item.user_id,
        creator: Array.isArray(item.creators) ? item.creators[0] : item.creators,
        trajectory: [],
        latestStats: item,
      })
    }

    const creatorData = creatorMap.get(item.user_id)
    creatorData.trajectory.push({
      date: item.recorded_date,
      followers: item.follower_count,
      growth: item.daily_growth_percent,
    })

    // Keep the most recent stats
    if (item.recorded_date > creatorData.latestStats.recorded_date) {
      creatorData.latestStats = item
    }
  })

  // Transform and calculate metrics
  const creators: RisingCreator[] = []

  creatorMap.forEach((creatorData) => {
    const { trajectory, latestStats, creator } = creatorData

    // Calculate metrics
    const growthDays = trajectory.filter((p: TrajectoryPoint) => p.growth > 0).length
    const totalDays = trajectory.length
    const avgGrowth =
      trajectory.reduce((sum: number, p: TrajectoryPoint) => sum + p.growth, 0) /
      totalDays

    const consistencyScore = calculateConsistencyScore(growthDays, totalDays)

    // Vibe Score = (hearts / followers) normalized to 0-10 scale
    const vibeScore =
      latestStats.follower_count > 0
        ? Math.min(
            (latestStats.heart_count / latestStats.follower_count) * 0.5,
            10
          )
        : 0

    // Hidden Gem: <50k followers but high average growth
    const isHiddenGem =
      latestStats.follower_count < 50000 && avgGrowth > 5 && consistencyScore !== 'Spike'

    // Apply filters (RELAXED for cold start)
    const meetsFilters =
      latestStats.follower_count < 100000 && // Still under 100k
      latestStats.daily_growth_percent >= 0 // Allow 0% on first day (changed from > 0)

    if (!meetsFilters) return

    // Optional category filter
    if (
      category &&
      category !== 'all' &&
      (!latestStats.source_trend ||
        !latestStats.source_trend.toLowerCase().includes(category.toLowerCase()))
    ) {
      return
    }

    creators.push({
      user_id: creatorData.user_id,
      handle: creator.handle,
      avatar_url: creator.avatar_url,
      nickname: creator.nickname,
      stats: {
        user_id: latestStats.user_id,
        follower_count: latestStats.follower_count,
        daily_growth_percent: latestStats.daily_growth_percent,
        heart_count: latestStats.heart_count,
        recorded_date: latestStats.recorded_date,
        source_trend: latestStats.source_trend,
      },
      trajectory,
      vibe_score: Math.round(vibeScore * 10) / 10,
      consistency_score: consistencyScore,
      growth_days: growthDays,
      avg_30d_growth: Math.round(avgGrowth * 10) / 10,
      is_hidden_gem: isHiddenGem,
      rank: 0, // Will be set after sorting
    })
  })

  // Sort by current velocity for cold start (prioritize active growth NOW)
  creators.sort((a, b) => {
    const aDaysOfHistory = a.trajectory.length
    const bDaysOfHistory = b.trajectory.length
    const aIsNew = aDaysOfHistory < 7
    const bIsNew = bDaysOfHistory < 7

    // If both are new OR both are mature, use daily growth percent
    // This ensures new creators show up immediately
    if ((aIsNew && bIsNew) || (!aIsNew && !bIsNew)) {
      // First by daily growth (current velocity)
      const growthDiff = b.stats.daily_growth_percent - a.stats.daily_growth_percent
      if (Math.abs(growthDiff) > 0.1) return growthDiff

      // Then by consistency if mature
      if (!aIsNew && !bIsNew) {
        const consistencyOrder: Record<ConsistencyRating, number> = {
          'A+': 4,
          A: 3,
          B: 2,
          C: 1,
          Spike: 0,
        }
        const consistencyDiff =
          consistencyOrder[b.consistency_score] - consistencyOrder[a.consistency_score]
        if (consistencyDiff !== 0) return consistencyDiff
      }

      // For cold start (all 0% growth), sort by follower count descending
      // This shows larger creators first when no growth data exists
      const followerDiff = b.stats.follower_count - a.stats.follower_count
      if (followerDiff !== 0) return followerDiff

      // Finally by 30d average
      return b.avg_30d_growth - a.avg_30d_growth
    }

    // Prioritize mature creators over new ones (if mature has good metrics)
    return bIsNew ? -1 : 1
  })

  // Assign ranks and limit to top 50
  return creators.slice(0, 50).map((creator, index) => ({
    ...creator,
    rank: index + 1,
  }))
}

/**
 * Get hidden gems - creators under 20k followers with high potential
 */
export async function getHiddenGems(): Promise<RisingCreator[]> {
  const today = new Date()
  const sevenDaysAgo = new Date(today)
  sevenDaysAgo.setDate(today.getDate() - 7)

  const todayStr = today.toISOString().split('T')[0]
  const sevenDaysAgoStr = sevenDaysAgo.toISOString().split('T')[0]

  const { data, error } = await supabase
    .from('creator_stats')
    .select(
      `
      user_id,
      follower_count,
      daily_growth_percent,
      heart_count,
      recorded_date,
      source_trend,
      creators!inner (
        handle,
        avatar_url,
        nickname
      )
    `
    )
    .lt('follower_count', 20000) // Under 20k
    .gt('follower_count', 1000) // At least 1k (not brand new)
    .gte('recorded_date', sevenDaysAgoStr)
    .lte('recorded_date', todayStr)
    .order('daily_growth_percent', { ascending: false })
    .limit(50)

  if (error || !data) {
    console.error('Error fetching hidden gems:', error)
    return []
  }

  // Group and dedupe by user_id
  const creatorMap = new Map<string, any>()
  
  data.forEach((item: any) => {
    if (!creatorMap.has(item.user_id)) {
      const creator = Array.isArray(item.creators) ? item.creators[0] : item.creators
      creatorMap.set(item.user_id, {
        user_id: item.user_id,
        handle: creator.handle,
        avatar_url: creator.avatar_url,
        nickname: creator.nickname,
        stats: {
          user_id: item.user_id,
          follower_count: item.follower_count,
          daily_growth_percent: item.daily_growth_percent,
          heart_count: item.heart_count,
          recorded_date: item.recorded_date,
          source_trend: item.source_trend,
        },
        trajectory: [],
        vibe_score: 0,
        consistency_score: 'B' as ConsistencyRating,
        growth_days: 0,
        avg_30d_growth: item.daily_growth_percent,
        is_hidden_gem: true,
        rank: 0,
      })
    }
  })

  return Array.from(creatorMap.values()).slice(0, 6)
}

export type TrendWithCount = {
  keyword: string
  displayName: string // Shortened display name
  creatorCount: number
  isHot: boolean // 3+ creators = hot trend
  childTrends?: string[] // Original trends that were grouped
}

/**
 * Extract core topic from a trend name for grouping
 * "Bad Bunny Song DtMF" → "bad bunny"
 * "Lady Gaga Performs 'Abracadabra' At Grammys" → "lady gaga"
 */
function extractCoreTopic(trend: string): string {
  const lower = trend.toLowerCase()
  // Also create a no-space version for matching "Badbunny" → "bad bunny"
  const noSpaces = lower.replace(/\s+/g, '')
  
  // Known entities to extract
  const knownEntities = [
    'bad bunny', 'lady gaga', 'billie eilish', 'taylor swift', 'ariana grande',
    'chappell roan', 'justin bieber', 'chief keef', 'bts', 'grammys',
    'aunty shakira', 'valentines day', 'micro bikini', 'liberian girl',
    'kendrick lamar', 'karol g', 'shakira', 'super bowl', 'iphone',
  ]
  
  for (const entity of knownEntities) {
    const entityNoSpaces = entity.replace(/\s+/g, '')
    // Match with spaces OR without spaces
    if (lower.includes(entity) || noSpaces.includes(entityNoSpaces)) {
      return entity
    }
  }
  
  // Otherwise, take first 2-3 significant words
  const words = lower
    .replace(/['']/g, '')
    .split(/\s+/)
    .filter(w => !['the', 'a', 'an', 'at', 'in', 'on', 'of', 'vs', 'and', 'to', 'for'].includes(w))
  
  return words.slice(0, 2).join(' ')
}

/**
 * Create a nice display name for a grouped trend
 */
function createDisplayName(coreTopic: string, trends: string[]): string {
  // Capitalize first letter of each word
  const capitalized = coreTopic
    .split(' ')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
  
  // Special formatting
  if (coreTopic === 'grammys') return 'Grammys 2026'
  if (coreTopic === 'valentines day') return "Valentine's Day"
  if (coreTopic === 'micro bikini') return 'Micro Bikinis'
  
  return capitalized
}

/**
 * Get trends with creator counts, grouped by core topic
 * Merges "Bad Bunny" + "Bad Bunny Song DtMF" into one trend
 */
export async function getActiveTrends(): Promise<TrendWithCount[]> {
  const { data, error } = await supabase
    .from('creators')
    .select('discovered_via_trend')
    .not('discovered_via_trend', 'is', null)

  if (error) {
    console.error('Error fetching active trends:', error)
    return []
  }

  // Count creators per original trend
  const rawTrendCounts = new Map<string, number>()
  data?.forEach((c) => {
    const trend = c.discovered_via_trend
    if (trend) {
      rawTrendCounts.set(trend, (rawTrendCounts.get(trend) || 0) + 1)
    }
  })

  // Group trends by core topic
  const groupedTrends = new Map<string, { count: number; originals: string[] }>()
  
  rawTrendCounts.forEach((count, trend) => {
    const core = extractCoreTopic(trend)
    const existing = groupedTrends.get(core) || { count: 0, originals: [] }
    existing.count += count
    existing.originals.push(trend)
    groupedTrends.set(core, existing)
  })

  // Convert to array with hot flag
  const trends: TrendWithCount[] = Array.from(groupedTrends.entries())
    .map(([coreTopic, { count, originals }]) => ({
      keyword: originals[0], // Use first original for filtering
      displayName: createDisplayName(coreTopic, originals),
      creatorCount: count,
      isHot: count >= 3,
      childTrends: originals.length > 1 ? originals : undefined,
    }))
    .sort((a, b) => {
      if (a.isHot !== b.isHot) return a.isHot ? -1 : 1
      if (a.creatorCount !== b.creatorCount) return b.creatorCount - a.creatorCount
      return a.displayName.localeCompare(b.displayName)
    })

  return trends
}
