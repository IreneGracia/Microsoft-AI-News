'use client'

import { useEffect } from 'react'

interface Props {
  text: string
  onDone: () => void
}

export default function Toast({ text, onDone }: Props) {
  useEffect(() => {
    if (!text) return
    const t = setTimeout(onDone, 2200)
    return () => clearTimeout(t)
  }, [text, onDone])

  if (!text) return null
  return <div className="toast">{text}</div>
}
