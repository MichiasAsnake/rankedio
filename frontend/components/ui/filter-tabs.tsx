'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface FilterTabsProps {
  currentCategory: string
  trends: string[]
}

export function FilterTabs({ currentCategory, trends }: FilterTabsProps) {
  // Build categories array with "All" first, then dynamic trends
  const categories = [
    { label: 'All', value: 'all' },
    ...trends.map((trend) => ({
      label: trend,
      value: trend,
    })),
  ]

  return (
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
                className="absolute inset-0 rounded-xl bg-white/10 ring-1 ring-white/20"
                transition={{
                  type: 'spring',
                  stiffness: 500,
                  damping: 30,
                }}
              />
            )}
            <span
              className={cn(
                'relative block px-6 py-2.5 text-sm font-semibold transition-colors',
                isActive ? 'text-white' : 'text-zinc-500 hover:text-zinc-300'
              )}
            >
              {category.label}
            </span>
          </Link>
        )
      })}
    </div>
  )
}
