'use client'

import { useState, useCallback } from 'react'
import type { Tweaks } from '@/types'

export function useTweaks(defaults: Tweaks): [Tweaks, (keyOrEdits: keyof Tweaks | Partial<Tweaks>, val?: unknown) => void] {
  const [values, setValues] = useState<Tweaks>(defaults)

  const setTweak = useCallback((keyOrEdits: keyof Tweaks | Partial<Tweaks>, val?: unknown) => {
    const edits = typeof keyOrEdits === 'object' && keyOrEdits !== null
      ? keyOrEdits
      : { [keyOrEdits]: val }
    setValues((prev) => ({ ...prev, ...edits }))
    if (typeof window !== 'undefined') {
      window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*')
    }
  }, [])

  return [values, setTweak]
}
