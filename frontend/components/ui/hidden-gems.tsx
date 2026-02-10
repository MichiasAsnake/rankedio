'use client'

import { motion } from 'framer-motion'
import { Gem, TrendingUp, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { RisingCreator } from '@/lib/supabase'
import { CreatorAvatar } from './creator-avatar'

interface HiddenGemsProps {
  creators: RisingCreator[]
}

export function HiddenGems({ creators }: HiddenGemsProps) {
  if (creators.length === 0) return null

  const formatCount = (count: number): string => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
    return count.toString()
  }

  return (
    <div className="mb-12">
      {/* Section Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20 ring-1 ring-indigo-500/30">
          <Gem className="h-5 w-5 text-indigo-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">Hidden Gems</h2>
          <p className="text-sm text-zinc-400">Under 20k followers, high potential</p>
        </div>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {creators.slice(0, 6).map((creator, index) => (
          <motion.div
            key={creator.user_id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="group relative overflow-hidden rounded-xl border border-indigo-500/20 bg-gradient-to-br from-indigo-900/20 via-zinc-900/80 to-purple-900/20 p-5 hover:border-indigo-500/40 transition-all"
          >
            {/* Glow effect */}
            <div className="absolute -top-12 -right-12 h-24 w-24 rounded-full bg-indigo-500/10 blur-2xl opacity-0 group-hover:opacity-100 transition-opacity" />
            
            <div className="relative flex items-start gap-4">
              {/* Avatar with TikTok Link */}
              <Link 
                href={`https://www.tiktok.com/@${creator.handle}`}
                target="_blank"
                rel="noopener noreferrer"
                className="relative group/avatar shrink-0"
              >
                <CreatorAvatar 
                  src={creator.avatar_url} 
                  handle={creator.handle} 
                  size={48}
                  className="border-indigo-500/30 transition-all group-hover/avatar:border-pink-500/50"
                />
                {/* Hover overlay */}
                <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/60 opacity-0 transition-opacity group-hover/avatar:opacity-100">
                  <ExternalLink className="h-4 w-4 text-white" />
                </div>
              </Link>

              <div className="flex-1 min-w-0">
                <Link 
                  href={`https://www.tiktok.com/@${creator.handle}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-white hover:text-indigo-400 transition-colors truncate block"
                >
                  @{creator.handle}
                </Link>
                {creator.nickname && (
                  <p className="text-sm text-zinc-500 truncate">{creator.nickname}</p>
                )}
                
                <div className="flex items-center gap-4 mt-2">
                  <div className="text-sm">
                    <span className="text-zinc-500">Followers: </span>
                    <span className="font-mono text-indigo-400">{formatCount(creator.stats.follower_count)}</span>
                  </div>
                  <div className="flex items-center gap-1 text-sm">
                    <TrendingUp className="h-3 w-3 text-green-400" />
                    <span className="font-mono text-green-400">+{creator.stats.daily_growth_percent.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Trend tag */}
            {creator.stats.source_trend && (
              <div className="mt-3 pt-3 border-t border-white/5">
                <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/10 px-2.5 py-1 text-xs font-medium text-purple-400 ring-1 ring-purple-500/20">
                  <Gem className="h-3 w-3" />
                  {creator.stats.source_trend}
                </span>
              </div>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  )
}
