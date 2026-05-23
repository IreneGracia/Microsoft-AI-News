'use client'

import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import { REGIONS_AUTH } from '@/constants/auth'
import type { Palette, Thread, User } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  threads: Thread[]
  activeId: string
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onPin: (id: string) => void
  user: User
  onLogout: () => void
}

export default function Sidebar({ palette, displayFont, newsFont, threads, activeId, onSelect, onNew, onDelete, onPin, user, onLogout }: Props) {
  const regionLabel = (REGIONS_AUTH.find((r) => r.id === user.region) || {}).label
  const initial = (user.name || 'M').trim().charAt(0).toLowerCase()

  return (
    <aside className="sidebar">
      <div className="side-head">
        <div className="brand">
          <MaiMark palette={palette} size={32} />
          <Wordmark palette={palette} displayFont={displayFont} newsFont={newsFont} size={26} />
        </div>
        <button className="new-btn" onClick={onNew} style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.12)' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New
        </button>
      </div>

      <div className="side-section-label" style={{ color: palette.muted }}>Today&apos;s threads</div>
      <ul className="thread-list">
        {[...threads].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0)).map((t) => (
          <li key={t.id} className="thread-row">
            <button
              className={`thread-item ${t.id === activeId ? 'active' : ''}`}
              onClick={() => onSelect(t.id)}
              style={{ color: palette.ink }}
            >
              {t.pinned && (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style={{ color: palette.accent, flexShrink: 0 }}>
                  <path d="M16 4a1 1 0 0 1 .707 1.707L14 8.414V13l2 4H8l2-4V8.414L7.293 5.707A1 1 0 0 1 8 4h8z"/>
                </svg>
              )}
              <span className="t-title">{t.title}</span>
              <span className="t-time" style={{ color: palette.muted }}>{t.time}</span>
            </button>
            <div className="thread-actions">
              <button className="thread-action-btn" title={t.pinned ? 'Unpin' : 'Pin'}
                onClick={(e) => { e.stopPropagation(); onPin(t.id) }}
                style={{ color: t.pinned ? palette.accent : palette.muted }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill={t.pinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2v7l2 3H6l2-3V2"/><line x1="12" y1="12" x2="12" y2="22"/><line x1="8" y1="2" x2="16" y2="2"/>
                </svg>
              </button>
              <button className="thread-action-btn" title="Delete"
                onClick={(e) => { e.stopPropagation(); onDelete(t.id) }}
                style={{ color: palette.muted }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
                </svg>
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="side-foot" style={{ color: palette.muted, borderColor: 'rgba(0,0,0,0.08)' }}>
        <div className="user-row">
          <div className="avatar" style={{ background: palette.accent, color: palette.bg }}>{initial}</div>
          <div className="user-meta">
            <div style={{ color: palette.ink }}>{user.name || 'Guest'}</div>
            <div>{user.department || 'No department'}{regionLabel ? ' · ' + regionLabel : ''}</div>
          </div>
          <button className="signout-btn" onClick={onLogout} title="Sign out" aria-label="Sign out" style={{ color: palette.muted }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 17l5-5-5-5" /><path d="M21 12H9" /><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  )
}
