'use client'

import { useState } from 'react'
import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import { REGIONS_AUTH } from '@/constants/auth'
import { TOPIC_GROUPS } from '@/constants/preferences'
import type { NewsFolder, Palette, User } from '@/types'

const topicMap = Object.fromEntries(
  TOPIC_GROUPS.flatMap((g) => g.items.map((i) => [i.id, i.label]))
)

const freqBg: Record<string, string> = {
  daily: 'rgba(0,120,80,0.12)',
  weekly: 'rgba(60,60,200,0.1)',
  breaking: 'rgba(200,50,50,0.1)',
}
const freqColor: Record<string, string> = {
  daily: '#1a7a50',
  weekly: '#2f2fb0',
  breaking: '#b02020',
}
const freqLabels: Record<string, string> = { daily: 'Daily', weekly: 'Weekly', breaking: 'Breaking' }

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  folders: NewsFolder[]
  activeFolderId: string
  activeThreadId: string
  onSelectThread: (folderId: string, threadId: string) => void
  onNewThread: (folderId: string) => void
  onDeleteThread: (folderId: string, threadId: string) => void
  onPinThread: (folderId: string, threadId: string) => void
  onDeleteFolder: (id: string) => void
  onOpenFolders: () => void
  user: User
  onLogout: () => void
}

export default function Sidebar({
  palette, displayFont, newsFont,
  folders, activeFolderId, activeThreadId,
  onSelectThread, onNewThread, onDeleteThread, onPinThread,
  onDeleteFolder, onOpenFolders,
  user, onLogout,
}: Props) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    () => new Set(folders.slice(0, 1).map((f) => f.id))
  )

  const toggle = (id: string) =>
    setExpandedIds((s) => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const regionLabel = (REGIONS_AUTH.find((r) => r.id === user.region) || {}).label
  const initial = (user.name || 'M').trim().charAt(0).toLowerCase()

  return (
    <aside className="sidebar">
      <div className="side-head">
        <div className="brand">
          <MaiMark palette={palette} size={32} />
          <Wordmark palette={palette} displayFont={displayFont} newsFont={newsFont} size={26} />
        </div>
      </div>

      <div className="side-section-label" style={{ color: palette.muted }}>Your folders</div>

      <ul className="folder-list">
        {folders.map((f) => {
          const expanded = expandedIds.has(f.id)
          const sortedThreads = [...f.threads].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))

          return (
            <li key={f.id} className="folder-group">
              {/* Folder header */}
              <div className="folder-row">
                <button
                  className="folder-item"
                  onClick={() => toggle(f.id)}
                  style={{ color: palette.ink }}
                >
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0, opacity: 0.4, transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
                    <path d="M8 4l8 8-8 8z"/>
                  </svg>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.55 }}>
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                  </svg>
                  <div className="folder-meta">
                    <span className="folder-name">{f.name}</span>
                    <span className="folder-topics" style={{ color: palette.muted }}>
                      {f.topics.map((t) => topicMap[t] || t).join(' · ')}
                    </span>
                  </div>
                  <span className="folder-freq" style={{ background: freqBg[f.frequency], color: freqColor[f.frequency], flexShrink: 0 }}>
                    {freqLabels[f.frequency]}
                  </span>
                </button>
                <button className="folder-del" title="Remove folder" style={{ color: palette.muted }}
                  onClick={(e) => { e.stopPropagation(); onDeleteFolder(f.id) }}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M18 6L6 18M6 6l12 12"/>
                  </svg>
                </button>
              </div>

              {/* Threads inside folder */}
              {expanded && (
                <ul className="thread-list folder-threads">
                  {sortedThreads.map((t) => (
                    <li key={t.id} className="thread-row">
                      <button
                        className={`thread-item ${t.id === activeThreadId && f.id === activeFolderId ? 'active' : ''}`}
                        onClick={() => onSelectThread(f.id, t.id)}
                        style={{ color: palette.ink, paddingLeft: 28 }}
                      >
                        {t.pinned && (
                          <svg width="9" height="9" viewBox="0 0 24 24" fill={freqColor[f.frequency]} style={{ flexShrink: 0 }}>
                            <path d="M16 4a1 1 0 0 1 .707 1.707L14 8.414V13l2 4H8l2-4V8.414L7.293 5.707A1 1 0 0 1 8 4h8z"/>
                          </svg>
                        )}
                        <span className="t-title">{t.title}</span>
                        <span className="t-time" style={{ color: palette.muted }}>{t.time}</span>
                      </button>
                      <div className="thread-actions">
                        <button className="thread-action-btn" title={t.pinned ? 'Unpin' : 'Pin'}
                          onClick={(e) => { e.stopPropagation(); onPinThread(f.id, t.id) }}
                          style={{ color: t.pinned ? freqColor[f.frequency] : palette.muted }}>
                          <svg width="11" height="11" viewBox="0 0 24 24" fill={t.pinned ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 2v7l2 3H6l2-3V2"/><line x1="12" y1="12" x2="12" y2="22"/><line x1="8" y1="2" x2="16" y2="2"/>
                          </svg>
                        </button>
                        <button className="thread-action-btn" title="Delete"
                          onClick={(e) => { e.stopPropagation(); onDeleteThread(f.id, t.id) }}
                          style={{ color: palette.muted }}>
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
                          </svg>
                        </button>
                      </div>
                    </li>
                  ))}

                  <li>
                    <button className="new-thread-btn" onClick={() => onNewThread(f.id)} style={{ color: palette.muted }}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <path d="M12 5v14M5 12h14"/>
                      </svg>
                      New conversation
                    </button>
                  </li>
                </ul>
              )}
            </li>
          )
        })}

        {folders.length === 0 && (
          <li style={{ padding: '12px 10px', fontSize: 12, color: palette.muted }}>
            No folders yet. Add one below.
          </li>
        )}
      </ul>

      <button className="add-folder-btn" onClick={onOpenFolders} style={{ color: palette.muted }}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        Add folder
      </button>

      <div className="side-foot" style={{ color: palette.muted, borderColor: 'rgba(0,0,0,0.08)' }}>
        <div className="user-row">
          <div className="avatar" style={{ background: palette.accent, color: palette.bg }}>{initial}</div>
          <div className="user-meta">
            <div style={{ color: palette.ink }}>{user.name || 'Guest'}</div>
            <div>{user.department || 'No department'}{regionLabel ? ' · ' + regionLabel : ''}</div>
          </div>
          <button className="signout-btn" onClick={onLogout} title="Sign out" style={{ color: palette.muted }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 17l5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            </svg>
          </button>
        </div>
      </div>
    </aside>
  )
}
