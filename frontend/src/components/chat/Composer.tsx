'use client'

import { useRef, useEffect } from 'react'
import type { Palette } from '@/types'

interface Props {
  value: string
  setValue: (v: string) => void
  onSend: () => void
  palette: Palette
  disabled: boolean
  webSearch: boolean
  onToggleWebSearch: () => void
}

export default function Composer({ value, setValue, onSend, palette, disabled, webSearch, onToggleWebSearch }: Props) {
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
        <textarea
          ref={taRef}
          className="composer-input"
          placeholder="Ask anything…"
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() } }}
          style={{ color: palette.ink }}
        />
        <button
          type="button"
          onClick={onToggleWebSearch}
          aria-pressed={webSearch}
          title={webSearch
            ? 'Web search fallback: ON — if no matching articles are found, the answer comes from a live web search'
            : 'Web search fallback: OFF — if no matching articles are found, the bot says it has no coverage'}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '6px 10px', borderRadius: 999, flexShrink: 0,
            border: `1.5px solid ${webSearch ? palette.accent : 'rgba(0,0,0,0.18)'}`,
            background: webSearch ? palette.accent : 'transparent',
            color: webSearch ? '#fff' : palette.muted,
            fontSize: 12, fontWeight: 600, cursor: 'pointer',
            transition: 'background 0.15s, border-color 0.15s, color 0.15s',
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          Web
        </button>
        <button type="submit" className="send-btn" disabled={disabled || !value.trim()}
          style={{ background: palette.ink, color: palette.bg }} aria-label="Send">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14" /><path d="m13 6 6 6-6 6" />
          </svg>
        </button>
      </div>
    </form>
  )
}
