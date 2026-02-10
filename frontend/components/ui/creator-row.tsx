'use client'

import { motion } from 'framer-motion'
import { TrendingUp, Sparkles, Gem, Award, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { RisingCreator, ConsistencyRating } from '@/lib/supabase'
import { cn } from '@/lib/utils'
import { TrajectorySparkline } from './trajectory-sparkline'
import { CreatorAvatar } from './creator-avatar'

interface CreatorRowProps {
  creator: RisingCreator
  index: number
}

export function CreatorRow({ creator, index }: CreatorRowProps) {
  const {
    rank,
    handle,
    nickname,
    avatar_url,
    stats,
    vibe_score,
    consistency_score,
    trajectory,
    avg_30d_growth,
    growth_days,
    is_hidden_gem,
  } = creator

  // Determine if creator is "New Arrival" or "Rising Star"
  const daysOfHistory = trajectory.length
  const isNewArrival = daysOfHistory < 3
  const isMature = daysOfHistory >= 7

  // Format numbers with K/M suffix
  const formatCount = (count: number): string => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
    return count.toString()
  }

  // Consistency badge styling
  const getConsistencyBadge = (
    rating: ConsistencyRating
  ): { label: string; color: string; bg: string; ring: string } => {
    switch (rating) {
      case 'A+':
        return {
          label: 'Steady Grower',
          color: 'text-emerald-400',
          bg: 'bg-emerald-500/10',
          ring: 'ring-emerald-500/20',
        }
      case 'A':
        return {
          label: 'Consistent',
          color: 'text-green-400',
          bg: 'bg-green-500/10',
          ring: 'ring-green-500/20',
        }
      case 'B':
        return {
          label: 'Growing',
          color: 'text-blue-400',
          bg: 'bg-blue-500/10',
          ring: 'ring-blue-500/20',
        }
      case 'C':
        return {
          label: 'Moderate',
          color: 'text-yellow-400',
          bg: 'bg-yellow-500/10',
          ring: 'ring-yellow-500/20',
        }
      case 'Spike':
        return {
          label: 'Viral Spike',
          color: 'text-orange-400',
          bg: 'bg-orange-500/10',
          ring: 'ring-orange-500/20',
        }
    }
  }

  const consistencyBadge = getConsistencyBadge(consistency_score)

  // Animation variants for staggered fade-up
  const rowVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.5,
        ease: [0.22, 1, 0.36, 1], // Custom easing
        delay: index * 0.05, // Stagger effect
      },
    },
  }

  return (
    <motion.div
      variants={rowVariants}
      initial="hidden"
      animate="visible"
      whileHover={{ scale: 1.01, transition: { duration: 0.2 } }}
      className={cn(
        'group relative',
        'flex flex-col gap-4 lg:grid lg:grid-cols-[80px_1fr_auto_auto_auto_auto_auto] lg:items-center lg:gap-6',
        'rounded-2xl border p-4 lg:p-6',
        'backdrop-blur-sm transition-all duration-300',
        is_hidden_gem
          ? 'border-indigo-500/30 bg-gradient-to-r from-indigo-900/20 via-zinc-900/50 to-purple-900/20 hover:border-indigo-500/50 hover:shadow-xl hover:shadow-indigo-500/10'
          : 'border-white/5 bg-zinc-900/50 hover:border-white/10 hover:bg-zinc-900/80 hover:shadow-xl hover:shadow-black/20'
      )}
    >
      {/* Hidden Gem Badge (Top Right Corner) */}
      {is_hidden_gem && (
        <div className="absolute right-4 top-4">
          <div className="flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-3 py-1 ring-1 ring-indigo-500/30">
            <Gem className="h-3.5 w-3.5 text-indigo-400" />
            <span className="text-xs font-semibold text-indigo-400">
              Hidden Gem
            </span>
          </div>
        </div>
      )}

      {/* MOBILE: Top row with rank, avatar, handle, growth */}
      <div className="flex items-center justify-between lg:hidden">
        <div className="flex items-center gap-3">
          {/* Mobile Rank */}
          <span
            className={cn(
              'font-mono text-2xl font-bold tabular-nums',
              rank <= 3
                ? 'bg-gradient-to-br from-yellow-400 to-amber-600 bg-clip-text text-transparent'
                : 'text-zinc-500'
            )}
          >
            #{rank}
          </span>
          {/* Mobile Avatar */}
          <Link 
            href={`https://www.tiktok.com/@${handle}`}
            target="_blank"
            rel="noopener noreferrer"
            className="relative"
          >
            <CreatorAvatar src={avatar_url} handle={handle} size={48} />
          </Link>
          {/* Mobile Handle */}
          <div className="flex flex-col">
            <Link 
              href={`https://www.tiktok.com/@${handle}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-white text-sm"
            >
              @{handle}
            </Link>
            <span className="text-xs text-zinc-500">{formatCount(stats.follower_count)} followers</span>
          </div>
        </div>
        {/* Mobile Growth Badge */}
        <div className="flex items-center gap-1.5 rounded-lg bg-green-500/10 px-3 py-1.5 ring-1 ring-green-500/20">
          <TrendingUp className="h-4 w-4 text-green-400" />
          <span className="font-mono text-sm font-bold tabular-nums text-green-400">
            +{isNewArrival ? stats.daily_growth_percent.toFixed(1) : avg_30d_growth.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* MOBILE: Bottom row with secondary stats */}
      <div className="flex items-center justify-between gap-4 lg:hidden">
        <div className="flex items-center gap-1">
          <Sparkles className="h-3 w-3 text-yellow-400" />
          <span className="text-xs text-zinc-400">Vibe: </span>
          <span className="font-mono text-xs font-semibold text-yellow-400">{vibe_score.toFixed(1)}</span>
        </div>
        <div className="flex items-center gap-1">
          <Award className={cn('h-3 w-3', consistencyBadge.color)} />
          <span className="text-xs text-zinc-400">Consistency: </span>
          <span className={cn('text-xs font-semibold', consistencyBadge.color)}>{consistency_score}</span>
        </div>
        {isMature && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-zinc-400">{growth_days}d growth</span>
          </div>
        )}
      </div>

      {/* DESKTOP: Rank */}
      <div className="hidden lg:flex items-center justify-center">
        <span
          className={cn(
            'font-mono text-4xl font-bold tabular-nums',
            rank <= 3
              ? 'bg-gradient-to-br from-yellow-400 to-amber-600 bg-clip-text text-transparent'
              : 'text-zinc-500'
          )}
        >
          #{rank.toString().padStart(2, '0')}
        </span>
      </div>

      {/* DESKTOP: Identity (Avatar + Handle + Nickname + Trend Badge) */}
      <div className="hidden lg:flex items-center gap-4">
        {/* Avatar + TikTok Link */}
        <Link 
          href={`https://www.tiktok.com/@${handle}`}
          target="_blank"
          rel="noopener noreferrer"
          className="relative group/avatar"
        >
          <div className="absolute -inset-0.5 rounded-full bg-gradient-to-br from-green-400/20 to-emerald-600/20 blur-sm transition-all group-hover/avatar:from-pink-500/30 group-hover/avatar:to-cyan-500/30" />
          <CreatorAvatar 
            src={avatar_url} 
            handle={handle} 
            size={56} 
            className="relative transition-all group-hover/avatar:border-pink-500/50"
          />
          {/* TikTok hover overlay */}
          <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/60 opacity-0 transition-opacity group-hover/avatar:opacity-100">
            <ExternalLink className="h-5 w-5 text-white" />
          </div>
        </Link>

        {/* Handle + Nickname + Badge */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Link 
              href={`https://www.tiktok.com/@${handle}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-white hover:text-pink-400 transition-colors flex items-center gap-1.5"
            >
              @{handle}
              <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-50" />
            </Link>
            {stats.source_trend && (
              <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/10 px-2 py-0.5 text-xs font-medium text-purple-400 ring-1 ring-purple-500/20">
                <Sparkles className="h-3 w-3" />
                {stats.source_trend}
              </span>
            )}
          </div>
          {nickname && (
            <span className="text-sm text-zinc-500">{nickname}</span>
          )}
        </div>
      </div>

      {/* DESKTOP: Weight Class (Followers) */}
      <div className="hidden lg:flex flex-col items-end gap-1">
        <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
          Followers
        </span>
        <span className="font-mono text-xl font-semibold tabular-nums text-zinc-300">
          {formatCount(stats.follower_count)}
        </span>
      </div>

      {/* DESKTOP: Vibe Check (Engagement Score) */}
      <div className="hidden lg:flex flex-col items-end gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            Vibe Check
          </span>
          <div className="flex items-center gap-1">
            <Sparkles className="h-3 w-3 text-yellow-400" />
            <span className="font-mono text-sm font-semibold tabular-nums text-yellow-400">
              {vibe_score.toFixed(1)}
            </span>
          </div>
        </div>
        {/* Progress bar */}
        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-zinc-800">
          <motion.div
            className="h-full bg-gradient-to-r from-yellow-400 to-amber-500"
            initial={{ width: 0 }}
            animate={{ width: `${(vibe_score / 10) * 100}%` }}
            transition={{ duration: 0.8, delay: index * 0.05 + 0.3 }}
          />
        </div>
      </div>

      {/* DESKTOP: Trajectory Section - Conditional: New Arrival vs Rising Star */}
      <div className="hidden lg:flex flex-col items-center gap-2">
        {isNewArrival ? (
          // NEW ARRIVAL: Show "Just Detected" badge instead of sparkline
          <>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Status
            </span>
            <div className="flex items-center gap-1.5 rounded-full bg-cyan-500/10 px-3 py-1.5 ring-1 ring-cyan-500/20">
              <Sparkles className="h-4 w-4 text-cyan-400" />
              <span className="text-sm font-semibold text-cyan-400">
                Just Detected
              </span>
            </div>
            <span className="text-xs text-zinc-600">{daysOfHistory}d history</span>
          </>
        ) : (
          // RISING STAR: Show sparkline
          <>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              30D Trajectory
            </span>
            <TrajectorySparkline data={trajectory} />
            <span className="text-xs text-zinc-600">{growth_days} growth days</span>
          </>
        )}
      </div>

      {/* DESKTOP: Consistency Score - Conditional */}
      <div className="hidden lg:flex flex-col items-end gap-2">
        {isNewArrival ? (
          // NEW ARRIVAL: Show "N/A" for consistency
          <>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Consistency
            </span>
            <div className="flex items-center gap-1.5 rounded-lg bg-zinc-800/50 px-3 py-2 ring-1 ring-zinc-700/50">
              <span className="text-sm font-semibold text-zinc-600">N/A</span>
            </div>
            <span className="text-xs text-zinc-600">Need 7+ days</span>
          </>
        ) : (
          // RISING STAR: Show consistency badge
          <>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Consistency
            </span>
            <div
              className={cn(
                'flex items-center gap-1.5 rounded-lg px-3 py-2 ring-1',
                consistencyBadge.bg,
                consistencyBadge.ring
              )}
            >
              <Award className={cn('h-4 w-4', consistencyBadge.color)} />
              <span className={cn('text-sm font-semibold', consistencyBadge.color)}>
                {consistencyBadge.label}
              </span>
            </div>
            <span className={cn('text-xs font-medium', consistencyBadge.color)}>
              {consistency_score}
            </span>
          </>
        )}
      </div>

      {/* DESKTOP: Growth Metric - Conditional: 24H for New, 30D Avg for Mature */}
      <div className="hidden lg:flex flex-col items-end gap-1">
        {isNewArrival ? (
          // NEW ARRIVAL: Show 24H Velocity
          <>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Velocity (24H)
            </span>
            <div className="flex items-center gap-2 rounded-xl bg-cyan-500/10 px-4 py-2.5 ring-1 ring-cyan-500/20">
              <TrendingUp className="h-5 w-5 text-cyan-400" />
              <span className="font-mono text-lg font-bold tabular-nums text-cyan-400">
                +{stats.daily_growth_percent.toFixed(1)}%
              </span>
            </div>
          </>
        ) : (
          // RISING STAR: Show 30D Average
          <>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              Avg Growth (30D)
            </span>
            <div className="flex items-center gap-2 rounded-xl bg-green-500/10 px-4 py-2.5 ring-1 ring-green-500/20">
              <TrendingUp className="h-5 w-5 text-green-400" />
              <span className="font-mono text-lg font-bold tabular-nums text-green-400">
                +{avg_30d_growth.toFixed(1)}%
              </span>
            </div>
          </>
        )}
      </div>

      {/* Hover effect gradient */}
      <div
        className={cn(
          'pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-r opacity-0 transition-opacity duration-300 group-hover:opacity-100',
          is_hidden_gem
            ? 'from-indigo-500/0 via-indigo-500/5 to-purple-500/0'
            : 'from-green-500/0 via-green-500/5 to-green-500/0'
        )}
      />
    </motion.div>
  )
}
