'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mail, Sparkles, Check, Loader2 } from 'lucide-react'

export function EmailSignup() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!email || !email.includes('@')) {
      setStatus('error')
      setMessage('Please enter a valid email')
      return
    }

    setStatus('loading')
    
    try {
      const res = await fetch('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      
      const data = await res.json()
      
      if (res.ok) {
        setStatus('success')
        setMessage('You\'re in! Watch your inbox for new Comets 🚀')
        setEmail('')
      } else {
        setStatus('error')
        setMessage(data.error || 'Something went wrong')
      }
    } catch (err) {
      setStatus('error')
      setMessage('Failed to subscribe. Try again!')
    }
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-indigo-900/30 via-zinc-900/80 to-purple-900/30 p-8">
      {/* Background glow */}
      <div className="absolute -top-24 -right-24 h-48 w-48 rounded-full bg-indigo-500/20 blur-3xl" />
      <div className="absolute -bottom-24 -left-24 h-48 w-48 rounded-full bg-purple-500/20 blur-3xl" />
      
      <div className="relative">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20 ring-1 ring-indigo-500/30">
            <Mail className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Get Comet Alerts</h3>
            <p className="text-sm text-zinc-400">New rising creators, delivered weekly</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="relative flex-1">
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (status === 'error') setStatus('idle')
              }}
              placeholder="you@example.com"
              disabled={status === 'loading' || status === 'success'}
              className="w-full rounded-xl border border-white/10 bg-zinc-900/50 px-4 py-3 text-white placeholder-zinc-500 outline-none transition-all focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-50"
            />
          </div>
          
          <motion.button
            type="submit"
            disabled={status === 'loading' || status === 'success'}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 px-6 py-3 font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-xl hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {status === 'loading' ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : status === 'success' ? (
              <>
                <Check className="h-5 w-5" />
                Subscribed
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5" />
                Subscribe
              </>
            )}
          </motion.button>
        </form>

        <AnimatePresence>
          {message && (
            <motion.p
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={`mt-3 text-sm ${
                status === 'error' ? 'text-red-400' : 'text-green-400'
              }`}
            >
              {message}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
