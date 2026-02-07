import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json()

    if (!email || !email.includes('@')) {
      return NextResponse.json(
        { error: 'Valid email required' },
        { status: 400 }
      )
    }

    // Use service role for insert (bypasses RLS)
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // Check if already subscribed
    const { data: existing } = await supabase
      .from('subscribers')
      .select('email')
      .eq('email', email.toLowerCase())
      .single()

    if (existing) {
      return NextResponse.json(
        { message: 'Already subscribed!', existing: true },
        { status: 200 }
      )
    }

    // Insert new subscriber
    const { error } = await supabase.from('subscribers').insert({
      email: email.toLowerCase(),
      subscribed_at: new Date().toISOString(),
      preferences: { weekly_digest: true, new_comets: true },
    })

    if (error) {
      console.error('Supabase insert error:', error)
      return NextResponse.json(
        { error: 'Failed to subscribe' },
        { status: 500 }
      )
    }

    return NextResponse.json(
      { message: 'Successfully subscribed!' },
      { status: 200 }
    )
  } catch (err) {
    console.error('Subscribe error:', err)
    return NextResponse.json(
      { error: 'Server error' },
      { status: 500 }
    )
  }
}
