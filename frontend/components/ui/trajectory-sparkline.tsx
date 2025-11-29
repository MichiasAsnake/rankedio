'use client'

import { LineChart, Line, ResponsiveContainer } from 'recharts'
import { TrajectoryPoint } from '@/lib/supabase'

interface TrajectorySparklineProps {
  data: TrajectoryPoint[]
  className?: string
}

export function TrajectorySparkline({
  data,
  className = '',
}: TrajectorySparklineProps) {
  // Transform data for recharts
  const chartData = data.map((point) => ({
    value: point.followers,
  }))

  // Determine if trajectory is positive (more growth than decline)
  const positiveGrowthCount = data.filter((p) => p.growth > 0).length
  const isPositiveTrend = positiveGrowthCount > data.length / 2

  return (
    <div className={`h-12 w-32 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={isPositiveTrend ? '#4ade80' : '#f97316'}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
