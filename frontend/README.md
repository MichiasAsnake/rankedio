# Comet Beta Dashboard 🚀

A high-end, dark mode SaaS dashboard for discovering rising TikTok creators (Comets) with viral velocity tracking.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS + clsx/tailwind-merge
- **Animation**: Framer Motion
- **Icons**: Lucide React
- **Backend**: Supabase (PostgreSQL)
- **Fonts**: Geist Sans & Geist Mono

## Features

✨ **Design System**
- Dark mode SaaS aesthetic
- Smooth, staggered fade-up animations (Motion Primitives inspired)
- Bento grid/card layout (Blocks.so inspired)
- Subtle dot-grid background pattern (Pattern Craft inspired)
- Tabular figures for perfect number alignment

🎯 **Data Integration**
- Real-time Supabase connection
- Fetches top 50 rising creators (Comets)
- Filters: Today's date, growth > 0%, followers < 100k
- Sorted by daily growth % (highest velocity first)

🎨 **UI Components**
- Hero header with headline and filter tabs
- Interactive leaderboard rows with:
  - Rank display
  - Avatar + handle + nickname
  - Trend badge (source_trend)
  - Stats cluster (followers, vibe score)
  - Velocity metric (24h growth %)
- Empty states
- Stats footer

## Getting Started

### 1. Install Dependencies

```bash
npm install
# or
yarn install
# or
pnpm install
```

### 2. Configure Environment Variables

Copy `.env.local.example` to `.env.local` and add your Supabase credentials:

```bash
cp .env.local.example .env.local
```

Edit `.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

### 3. Install Geist Font (Optional but Recommended)

```bash
npm install geist
```

### 4. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout with Geist fonts
│   ├── page.tsx            # Main dashboard (server component)
│   └── globals.css         # Global styles + Tailwind
├── components/
│   └── ui/
│       ├── creator-row.tsx # Animated leaderboard row
│       └── filter-tabs.tsx # Category filter tabs
├── lib/
│   ├── supabase.ts         # Supabase client + data fetching
│   └── utils.ts            # cn() utility (clsx + tailwind-merge)
├── tailwind.config.ts      # Tailwind config with custom animations
└── package.json
```

## Database Schema

The dashboard expects these Supabase tables:

### `creators`
- `user_id` (VARCHAR, PRIMARY KEY)
- `handle` (VARCHAR)
- `avatar_url` (TEXT, nullable)
- `nickname` (VARCHAR, nullable)

### `creator_stats`
- `user_id` (VARCHAR, FOREIGN KEY)
- `follower_count` (BIGINT)
- `daily_growth_percent` (DECIMAL)
- `heart_count` (BIGINT)
- `recorded_date` (DATE)
- `source_trend` (VARCHAR, nullable)

### `daily_trends`
- `trend_keyword` (VARCHAR)
- `discovered_at` (DATE)
- `rank` (INT)

## Key Design Decisions

### Typography
- **Geist Sans**: Primary UI font (clean, modern)
- **Geist Mono**: Numbers and monospace elements
- **Tabular Figures**: All numbers use `tabular-nums` for perfect vertical alignment

### Color Palette
- **Background**: `zinc-950` with radial gradient
- **Cards**: `zinc-900/50` with backdrop blur
- **Borders**: `white/5` to `white/10` on hover
- **Accent**: Green (`green-400` to `emerald-600`) for growth metrics
- **Secondary**: Purple for trend badges, Yellow for vibe scores

### Animations
- **Staggered Fade-Up**: Rows cascade in with 50ms delay between each
- **Hover Effects**: Subtle scale (1.01) and shadow on row hover
- **Progress Bars**: Delayed animation for vibe score visualization
- **Tab Transitions**: Spring animation with layoutId for smooth category switching

### Components

#### `CreatorRow`
- **Grid Layout**: `80px | 1fr | auto | auto | auto` for consistent spacing
- **Rank**: Large, bold, gradient for top 3
- **Avatar**: Circular with subtle green glow effect
- **Trend Badge**: Optional, only shows if `source_trend` exists
- **Vibe Score**: Calculated as `(hearts / followers) * 0.5`, capped at 10
- **Velocity**: Bright green pill with growth percentage

#### `FilterTabs`
- Segmented control with pill-shaped active state
- Framer Motion `layoutId` for smooth tab transitions
- Client component for interactivity

## Customization

### Adjust Vibe Score Calculation

Edit `lib/supabase.ts`:

```typescript
const vibeScore = stats.follower_count > 0
  ? Math.min((stats.heart_count / stats.follower_count) * 0.5, 10)
  : 0
```

### Add More Filter Categories

Edit `components/ui/filter-tabs.tsx`:

```typescript
const categories = [
  { label: 'All', value: 'all' },
  { label: 'Your Category', value: 'yourcategory' },
  // ...
]
```

### Change Animation Timing

Edit `components/ui/creator-row.tsx`:

```typescript
delay: index * 0.05, // Adjust stagger delay (currently 50ms)
```

## Performance

- **Server Components**: Main page fetches data server-side
- **Revalidation**: Auto-revalidates every 60 seconds
- **Client Components**: Only interactive UI (tabs, rows) use client-side rendering
- **Image Optimization**: Next.js Image component for avatars

## Empty States

The dashboard gracefully handles:
- No creators found (shows empty state with icon)
- Missing avatars (shows initials fallback)
- No trend badge (badge hidden if `source_trend` is null)
- Zero stats (displays "0" instead of breaking)

## Production Deployment

### Vercel (Recommended)

```bash
vercel
```

### Other Platforms

```bash
npm run build
npm run start
```

## Environment Variables for Production

Ensure these are set in your hosting platform:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Troubleshooting

### "No rising creators found"

**Possible causes**:
1. No data for today's date in `creator_stats`
2. All creators have `daily_growth_percent <= 0`
3. All creators have `follower_count >= 100000`

**Solution**: Run your ETL pipeline to populate today's data

### Supabase Connection Error

**Cause**: Invalid credentials or network issue

**Solution**:
1. Verify `.env.local` has correct Supabase URL and key
2. Check Supabase dashboard for project status
3. Ensure anon key has read permissions for tables

### Fonts Not Loading

**Cause**: Geist fonts not installed

**Solution**:
```bash
npm install geist
```

## License

Proprietary - Comet Beta Dashboard

## Support

For issues or questions, check the main project README or contact the development team.
