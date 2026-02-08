'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { Flame } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TrendWithCount } from '@/lib/supabase'

interface FilterTabsProps {
  currentCategory: string
  trends: TrendWithCount[]
}

export function FilterTabs({ currentCategory, trends }: FilterTabsProps) {
  // Build categories array with "All" first, then dynamic trends
  const categories = [
    { label: 'All', value: 'all', count: 0, isHot: false, childTrends: undefined as string[] | undefined },
    ...trends.map((trend) => ({
      label: trend.displayName,
      value: trend.keyword, // Use original keyword for URL filtering
      count: trend.creatorCount,
      isHot: trend.isHot,
      childTrends: trend.childTrends,
    })),
  ]

  return (
    <div className="space-y-3">
      {/* Hot Topics Banner */}
      {trends.some(t => t.isHot) && (
        <div className="flex items-center gap-2 text-sm">
          <Flame className="h-4 w-4 text-orange-500" />
          <span className="text-orange-400 font-medium">Hot Topics</span>
          <span className="text-zinc-500">— Multiple creators trending together</span>
        </div>
      )}
      
      <div className="inline-flex flex-wrap gap-2 rounded-2xl bg-zinc-900/50 p-1.5 ring-1 ring-white/5">
        {categories.map((category) => {
          const isActive =
            currentCategory === category.value ||
            (!currentCategory && category.value === 'all')

          return (
            <Link
              key={category.value}
              href={`/?category=${category.value}`}
              className="relative"
            >
              {isActive && (
                <motion.div
                  layoutId="activeTab"
                  className={cn(
                    "absolute inset-0 rounded-xl ring-1",
                    category.isHot 
                      ? "bg-orange-500/20 ring-orange-500/30" 
                      : "bg-white/10 ring-white/20"
                  )}
                  transition={{
                    type: 'spring',
                    stiffness: 500,
                    damping: 30,
                  }}
                />
              )}
              <span
                className={cn(
                  'relative flex items-center gap-1.5 px-4 py-2.5 text-sm font-semibold transition-colors',
                  isActive ? 'text-white' : 'text-zinc-500 hover:text-zinc-300'
                )}
              >
                {category.isHot && (
                  <Flame className="h-3.5 w-3.5 text-orange-500" />
                )}
                {category.label}
                {category.count > 0 && (
                  <span className={cn(
                    "ml-1 text-xs px-1.5 py-0.5 rounded-full",
                    category.isHot 
                      ? "bg-orange-500/20 text-orange-400"
                      : "bg-zinc-800 text-zinc-500"
                  )}>
                    {category.count}
                  </span>
                )}
              </span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
