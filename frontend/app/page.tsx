import { getRisingCreators, getActiveTrends, getHiddenGems } from '@/lib/supabase'
import { CreatorRow } from '@/components/ui/creator-row'
import { FilterTabs } from '@/components/ui/filter-tabs'
import { HiddenGems } from '@/components/ui/hidden-gems'
import { HotTopics } from '@/components/ui/hot-topics'
import { EmailSignup } from '@/components/ui/email-signup'
import { Rocket, TrendingUp } from 'lucide-react'

export const dynamic = 'force-dynamic'
export const revalidate = 60 // Revalidate every 60 seconds

export default async function Home({
  searchParams,
}: {
  searchParams: { category?: string }
}) {
  const category = searchParams.category || 'all'

  // Fetch creators, trends, and hidden gems in parallel
  const [creators, trends, hiddenGems] = await Promise.all([
    getRisingCreators(category === 'all' ? null : category),
    getActiveTrends(),
    getHiddenGems(),
  ])

  return (
    <main className="relative min-h-screen bg-zinc-950">
      {/* Background Pattern */}
      <div className="fixed inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(17,24,39,1),rgba(0,0,0,1))]" />
      <div
        className="fixed inset-0 opacity-30"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgb(255 255 255 / 0.05) 1px, transparent 0)`,
          backgroundSize: '40px 40px',
        }}
      />

      {/* Content */}
      <div className="relative">
        {/* Header */}
        <header className="border-b border-white/5 bg-zinc-950/50 backdrop-blur-xl">
          <div className="mx-auto max-w-7xl px-6 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
              
                <span className="text-xl font-bold text-white">Comet ☄️</span>
              </div>
              <button className="rounded-xl bg-white/5 px-4 py-2 text-sm font-medium text-white ring-1 ring-white/10 transition-all hover:bg-white/10">
                Connect Wallet
              </button>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <div className="mx-auto max-w-7xl px-6 py-16">
          <div className="mb-12 space-y-6">
            {/* Headline */}
            <h1 className="text-6xl font-bold leading-tight">
              <span className="text-white">Scout creator</span>
              <br />
              <span className="bg-gradient-to-r from-green-400 via-emerald-400 to-teal-400 bg-clip-text text-transparent">
                trajectories.
              </span>
            </h1>

            {/* Subhead */}
            <p className="max-w-2xl text-xl text-zinc-400">
              Track long-term growth patterns, not viral spikes. Discover
              consistent creators building sustainable careers.
            </p>

            {/* Filter Tabs */}
            <FilterTabs currentCategory={category} trends={trends} />
          </div>

          {/* Hot Topics Section */}
          {category === 'all' && <HotTopics trends={trends} />}

          {/* Hidden Gems Section */}
          {category === 'all' && hiddenGems.length > 0 && (
            <HiddenGems creators={hiddenGems} />
          )}

          {/* Email Signup */}
          <div className="mb-12">
            <EmailSignup />
          </div>

          {/* Leaderboard */}
          <div className="space-y-4">
            {/* Column Headers */}
            <div className="grid grid-cols-[80px_1fr_auto_auto_auto_auto_auto] gap-6 px-6 pb-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                Rank
              </div>
              <div className="text-xs font-semibold uppercase tracking-wider text-zinc-600">
                Creator Identity
              </div>
              <div className="text-right text-xs font-semibold uppercase tracking-wider text-zinc-600">
                Weight Class
              </div>
              <div className="text-right text-xs font-semibold uppercase tracking-wider text-zinc-600">
                Vibe Check
              </div>
              <div className="text-center text-xs font-semibold uppercase tracking-wider text-zinc-600">
                30D Trajectory
              </div>
              <div className="text-right text-xs font-semibold uppercase tracking-wider text-zinc-600">
                Consistency
              </div>
              <div className="text-right text-xs font-semibold uppercase tracking-wider text-zinc-600">
                Avg Growth (30D)
              </div>
            </div>

            {/* Creator Rows */}
            {creators.length > 0 ? (
              <div className="space-y-3">
                {creators.map((creator, index) => (
                  <CreatorRow
                    key={creator.user_id}
                    creator={creator}
                    index={index}
                  />
                ))}
              </div>
            ) : (
              // Empty State
              <div className="flex flex-col items-center justify-center rounded-2xl border border-white/5 bg-zinc-900/50 p-16 backdrop-blur-sm">
                <TrendingUp className="mb-4 h-12 w-12 text-zinc-700" />
                <h3 className="mb-2 text-xl font-semibold text-zinc-400">
                  No rising creators found
                </h3>
                <p className="text-center text-sm text-zinc-600">
                  No creators with sustained growth trajectories found.
                  <br />
                  Try a different category or check back as data accumulates.
                </p>
              </div>
            )}
          </div>

          {/* Stats Footer */}
          {creators.length > 0 && (
            <div className="mt-8 grid grid-cols-3 gap-4">
              <div className="rounded-xl border border-white/5 bg-zinc-900/50 p-6 backdrop-blur-sm">
                <div className="text-sm text-zinc-500">Total Comets</div>
                <div className="mt-2 font-mono text-3xl font-bold text-white">
                  {creators.length}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-zinc-900/50 p-6 backdrop-blur-sm">
                <div className="text-sm text-zinc-500">Avg. 30D Growth</div>
                <div className="mt-2 font-mono text-3xl font-bold text-green-400">
                  +
                  {(
                    creators.reduce((sum, c) => sum + c.avg_30d_growth, 0) /
                    creators.length
                  ).toFixed(1)}
                  %
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-zinc-900/50 p-6 backdrop-blur-sm">
                <div className="text-sm text-zinc-500">Top Performer</div>
                <div className="mt-2 font-mono text-3xl font-bold text-yellow-400">
                  @{creators[0]?.handle || 'N/A'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
