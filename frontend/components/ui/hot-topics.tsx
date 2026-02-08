'use client'

import { motion } from 'framer-motion'
import { Flame, TrendingUp, Users } from 'lucide-react'
import Link from 'next/link'
import { TrendWithCount } from '@/lib/supabase'

interface HotTopicsProps {
  trends: TrendWithCount[]
}

export function HotTopics({ trends }: HotTopicsProps) {
  const hotTrends = trends.filter(t => t.isHot)
  
  if (hotTrends.length === 0) return null

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-500/20 ring-1 ring-orange-500/30">
          <Flame className="h-4 w-4 text-orange-500" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-white">Hot Topics Right Now</h2>
          <p className="text-xs text-zinc-500">Multiple creators trending together = opportunity</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {hotTrends.map((trend, index) => (
          <motion.div
            key={trend.keyword}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Link
              href={`/?category=${encodeURIComponent(trend.keyword)}`}
              className="group block p-4 rounded-xl border border-orange-500/20 bg-gradient-to-br from-orange-900/20 via-zinc-900/80 to-red-900/20 hover:border-orange-500/40 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Flame className="h-4 w-4 text-orange-500" />
                    <span className="text-sm font-semibold text-white group-hover:text-orange-400 transition-colors">
                      {trend.displayName}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-zinc-500">
                    <span className="flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      {trend.creatorCount} creators
                    </span>
                    {trend.childTrends && trend.childTrends.length > 1 && (
                      <span className="text-zinc-600">
                        {trend.childTrends.length} variations
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-500/10 text-orange-400 font-bold text-sm">
                  {trend.creatorCount}
                </div>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
