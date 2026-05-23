'use client'

import { useRef, useEffect } from 'react'
import MaiMark from '@/components/ui/MaiMark'
import type { Palette } from '@/types'

interface Props {
  value: string
  setValue: (v: string) => void
  onSend: () => void
  palette: Palette
  disabled: boolean
}

export default function Composer({ value, setValue, onSend, palette, disabled }: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 220) + 'px'
  }, [value])

  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); onSend() }}>
      <div className="composer-inner" style={{ background: 'rgba(255,253,247,0.86)' }}>
        <MaiMark palette={palette} size={28} />
        <textarea
          ref={taRef}
          className="composer-input"
          placeholder="Ask about a model, a benchmark, a paper…"
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() } }}
          style={{ color: palette.ink }}
        />
        <div className="composer-actions">
          <button type="button" className="icon-btn" title="Voice" aria-label="Voice" style={{ color: palette.muted }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" />
            </svg>
          </button>
          <button type="submit" className="send-btn" disabled={disabled || !value.trim()}
            style={{ background: palette.ink, color: palette.bg }} aria-label="Send">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14" /><path d="m13 6 6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="composer-foot" style={{ color: palette.muted }}>
        <span>MAI reads widely but isn&apos;t always right. Cross-check what matters. Press <kbd>↵</kbd> to send.</span>
      </div>
    </form>
  )
}
