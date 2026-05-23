'use client'

import { useEffect, useRef } from 'react'
import type { ChatMessage, Palette } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  palette: Palette
  title: string
  messages: ChatMessage[]
}

function buildText(title: string, messages: ChatMessage[]): string {
  const lines: string[] = [`MAI News — ${title}`, '']
  for (const m of messages) {
    if (m.thinking || !m.content) continue
    lines.push(m.role === 'user' ? `You: ${m.content}` : `MAI: ${m.content}`)
    if (m.cards?.length) {
      lines.push('')
      m.cards.forEach((c) => lines.push(`  • ${c.title} (${c.source})`))
    }
    lines.push('')
  }
  return lines.join('\n')
}

function buildHtml(title: string, messages: ChatMessage[]): string {
  const rows = messages
    .filter((m) => !m.thinking && m.content)
    .map((m) => {
      const cards = m.cards?.length
        ? `<ul style="margin:8px 0 0 0;padding:0 0 0 18px;">${m.cards.map((c) => `<li>${c.title} <span style="color:#888">(${c.source})</span></li>`).join('')}</ul>`
        : ''
      const label = m.role === 'user' ? 'You' : 'MAI'
      const bg = m.role === 'user' ? '#f5f3ee' : '#fff'
      return `<div style="margin-bottom:20px;padding:14px 18px;background:${bg};border-radius:10px;"><strong>${label}</strong><p style="margin:6px 0 0;white-space:pre-wrap;">${m.content}</p>${cards}</div>`
    }).join('')

  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
  <style>body{font-family:'Inter Tight',system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 24px;color:#1f1d18;}h1{font-size:22px;margin-bottom:24px;}</style>
  </head><body><h1>MAI News — ${title}</h1>${rows}</body></html>`
}

export default function ShareModal({ open, onClose, palette, title, messages }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose() }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, onClose])

  if (!open) return null

  const handlePdf = () => {
    const html = buildHtml(title, messages)
    const win = window.open('', '_blank')
    if (!win) return
    win.document.write(html)
    win.document.close()
    win.focus()
    setTimeout(() => { win.print() }, 400)
    onClose()
  }

  const handleEmail = () => {
    const body = encodeURIComponent(buildText(title, messages))
    const subject = encodeURIComponent(`MAI News — ${title}`)
    window.location.href = `mailto:?subject=${subject}&body=${body}`
    onClose()
  }

  return (
    <div className="share-overlay">
      <div className="share-menu" ref={ref} style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.1)', color: palette.ink }}>
        <div className="share-title" style={{ color: palette.muted }}>Share conversation</div>
        <button className="share-option" onClick={handlePdf} style={{ color: palette.ink }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 18 15 15"/>
          </svg>
          Download as PDF
        </button>
        <button className="share-option" onClick={handleEmail} style={{ color: palette.ink }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
          </svg>
          Share by email
        </button>
      </div>
    </div>
  )
}
