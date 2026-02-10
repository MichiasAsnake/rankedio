'use client'

import { useState } from 'react'
import Image from 'next/image'
import { cn } from '@/lib/utils'

interface CreatorAvatarProps {
  src: string | null | undefined
  handle: string
  size?: number
  className?: string
}

export function CreatorAvatar({ src, handle, size = 56, className }: CreatorAvatarProps) {
  const [hasError, setHasError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const showFallback = !src || hasError

  // Generate a consistent color from handle
  const getColorFromHandle = (handle: string) => {
    const colors = [
      'from-pink-500 to-rose-500',
      'from-purple-500 to-indigo-500', 
      'from-blue-500 to-cyan-500',
      'from-teal-500 to-emerald-500',
      'from-amber-500 to-orange-500',
      'from-red-500 to-pink-500',
    ]
    const index = handle.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
    return colors[index % colors.length]
  }

  return (
    <div 
      className={cn(
        "relative overflow-hidden rounded-full border-2 border-zinc-800 bg-zinc-800",
        className
      )}
      style={{ width: size, height: size }}
    >
      {showFallback ? (
        <div 
          className={cn(
            "flex h-full w-full items-center justify-center bg-gradient-to-br font-bold text-white",
            getColorFromHandle(handle)
          )}
          style={{ fontSize: size * 0.4 }}
        >
          {handle[0]?.toUpperCase() || '?'}
        </div>
      ) : (
        <>
          {isLoading && (
            <div className="absolute inset-0 animate-pulse bg-zinc-700" />
          )}
          <Image
            src={src}
            alt={handle}
            fill
            className={cn(
              "object-cover transition-opacity duration-300",
              isLoading ? "opacity-0" : "opacity-100"
            )}
            sizes={`${size}px`}
            onLoad={() => setIsLoading(false)}
            onError={() => {
              setHasError(true)
              setIsLoading(false)
            }}
          />
        </>
      )}
    </div>
  )
}
