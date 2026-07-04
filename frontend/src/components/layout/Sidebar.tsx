'use client'

import { useState, useRef, useEffect } from 'react'
import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import { REGIONS_AUTH } from '@/constants/auth'
import type { NewsFolder, Palette, Thread, User } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  folders: NewsFolder[]
  activeFolderId: string | null
  activeThreadId: string
  generalThreads: Thread[]
  currentView: 'dashboard' | 'chat' | 'saved'
  onSetView: (v: 'dashboard' | 'chat' | 'saved') => void
  onSelectThread: (folderId: string | null, threadId: string) => void
  onNewThread: (folderId: string) => void
  onDeleteThread: (folderId: string, threadId: string) => void
  onNewChat: () => void
  onDeleteGeneralThread: (threadId: string) => void
  onDeleteFolder: (id: string) => void
  onAddFolder: (name: string) => void
  onRenameFolder: (id: string, name: string) => void
  onMoveThread: (sessionId: string, fromFolderId: string | null, toFolderId: string) => void
  user: User
  roleLabel?: string
  onLogout: () => void
}

export default function Sidebar({
  palette, displayFont, newsFont,
  folders, activeFolderId, activeThreadId,
  generalThreads, currentView, onSetView,
  onSelectThread, onNewThread, onDeleteThread,
  onNewChat, onDeleteGeneralThread,
  onDeleteFolder, onAddFolder,
  onRenameFolder, onMoveThread,
  user, roleLabel, onLogout,
}: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({ chats: true, projects: true })
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    () => new Set(folders.slice(0, 1).map((f) => f.id))
  )
  const [addingFolder, setAddingFolder] = useState(false)
  const [folderInput, setFolderInput] = useState('')
  const folderInputRef = useRef<HTMLInputElement>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameInput, setRenameInput] = useState('')
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null)

  const submitRename = () => {
    const name = renameInput.trim()
    if (name && renamingId) onRenameFolder(renamingId, name)
    setRenamingId(null)
    setRenameInput('')
  }

  const threadDragProps = (threadId: string, fromFolderId: string | null) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      e.dataTransfer.setData('application/x-mai-thread', JSON.stringify({ sessionId: threadId, fromFolderId }))
      e.dataTransfer.effectAllowed = 'move'
    },
  })

  const folderDropProps = (folderId: string) => ({
    onDragOver: (e: React.DragEvent) => {
      if (e.dataTransfer.types.includes('application/x-mai-thread')) {
        e.preventDefault()
        e.dataTransfer.dropEffect = 'move'
        setDragOverFolderId(folderId)
      }
    },
    onDragLeave: () => setDragOverFolderId((id) => (id === folderId ? null : id)),
    onDrop: (e: React.DragEvent) => {
      setDragOverFolderId(null)
      const raw = e.dataTransfer.getData('application/x-mai-thread')
      if (!raw) return
      e.preventDefault()
      try {
        const { sessionId, fromFolderId } = JSON.parse(raw)
        onMoveThread(sessionId, fromFolderId ?? null, folderId)
      } catch { /* malformed payload — ignore */ }
    },
  })

  useEffect(() => {
    if (addingFolder) folderInputRef.current?.focus()
  }, [addingFolder])

  const submitNewFolder = () => {
    const name = folderInput.trim()
    if (name) onAddFolder(name)
    setFolderInput('')
    setAddingFolder(false)
  }

  const toggleSection = (key: string) =>
    setOpen((s) => ({ ...s, [key]: !s[key] }))

  const toggleFolder = (id: string) =>
    setExpandedIds((s) => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const regionLabel = (REGIONS_AUTH.find((r) => r.id === user.region) || {}).label
  const initial = (user.name || 'M').trim().charAt(0).toLowerCase()

  const recentItems = [
    ...generalThreads.map((t) => ({ thread: t, folderId: null as string | null, folderName: null as string | null })),
    ...folders.flatMap((f) => f.threads.slice(0, 2).map((t) => ({ thread: t, folderId: f.id, folderName: f.name }))),
  ].slice(0, 10)

  const chevron = (expanded: boolean) => (
    <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor"
      style={{ opacity: 0.3, transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s', flexShrink: 0 }}>
      <path d="M8 4l8 8-8 8z" />
    </svg>
  )

  const sectionHd = (key: string, icon: React.ReactNode, label: string, onNav?: () => void, active?: boolean) => (
    <button
      className={`snav-hd ${active ? 'snav-nav-active' : ''}`}
      onClick={() => { toggleSection(key); onNav?.() }}
      style={{ color: active ? palette.ink : palette.ink }}
    >
      <span className="snav-icon" style={{ color: palette.muted }}>{icon}</span>
      <span className="snav-label">{label}</span>
      {chevron(!!open[key])}
    </button>
  )

  return (
    <aside className="sidebar">
      <div className="side-head">
        <div className="brand">
          <MaiMark palette={palette} size={32} />
          <Wordmark palette={palette} displayFont={displayFont} newsFont={newsFont} size={26} />
        </div>
      </div>

      <div className="sidebar-scroll" style={{ paddingBottom: 4 }}>
        {/* ── Dashboard ── */}
        <div className="snav-section">
          <button
            className={`snav-hd snav-nav-item ${currentView === 'dashboard' ? 'snav-nav-active' : ''}`}
            onClick={() => onSetView('dashboard')}
            style={{ color: currentView === 'dashboard' ? palette.ink : palette.muted }}
          >
            <span className="snav-icon">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
              </svg>
            </span>
            <span className="snav-label">Dashboard</span>
          </button>
        </div>

        {/* ── Chats ── */}
        <div className="snav-section">
          {sectionHd('chats',
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>,
            'Chats',
            () => onSetView('chat'),
            currentView === 'chat',
          )}
          {open.chats && (
            <div className="snav-body">
              <button className="snav-new-btn" onClick={onNewChat} style={{ color: palette.muted }}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
                New chat
              </button>
            </div>
          )}
        </div>

        {/* ── Projects ── */}
        <div className="snav-section">
          {sectionHd('projects',
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>,
            'Projects'
          )}
          {open.projects && (
            <div className="snav-body">
              <ul className="folder-list">
                {folders.map((f) => {
                  const expanded = expandedIds.has(f.id)
                  return (
                    <li key={f.id} className="folder-group">
                      <div className="folder-row" {...folderDropProps(f.id)}
                        style={dragOverFolderId === f.id
                          ? { outline: `1.5px dashed ${palette.accent}`, outlineOffset: -1, borderRadius: 8, background: 'rgba(0,0,0,0.045)' }
                          : undefined}>
                        {renamingId === f.id ? (
                          <div className="add-folder-form" style={{ flex: 1 }}>
                            <input
                              className="add-folder-input"
                              autoFocus
                              value={renameInput}
                              onChange={(e) => setRenameInput(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') submitRename()
                                if (e.key === 'Escape') { setRenamingId(null); setRenameInput('') }
                              }}
                              onBlur={submitRename}
                              style={{ color: palette.ink, borderColor: palette.accent }}
                            />
                          </div>
                        ) : (
                          <>
                            <button className="folder-item" onClick={() => toggleFolder(f.id)} style={{ color: palette.ink }}>
                              {chevron(expanded)}
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.55 }}>
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                              </svg>
                              <div className="folder-meta">
                                <span className="folder-name">{f.name}</span>
                              </div>
                            </button>
                            <button className="folder-del" title="Rename folder" style={{ color: palette.muted }}
                              onClick={(e) => { e.stopPropagation(); setRenamingId(f.id); setRenameInput(f.name) }}>
                              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>
                              </svg>
                            </button>
                            <button className="folder-del" title="Remove folder" style={{ color: palette.muted }}
                              onClick={(e) => { e.stopPropagation(); onDeleteFolder(f.id) }}>
                              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                                <path d="M18 6L6 18M6 6l12 12"/>
                              </svg>
                            </button>
                          </>
                        )}
                      </div>

                      {expanded && (
                        <ul className="thread-list folder-threads">
                          {f.threads.map((t) => (
                            <li key={t.id} className="thread-row">
                              <button
                                className={`thread-item ${t.id === activeThreadId && f.id === activeFolderId ? 'active' : ''}`}
                                onClick={() => onSelectThread(f.id, t.id)}
                                style={{ color: palette.ink }}
                                {...threadDragProps(t.id, f.id)}
                              >
                                <span className="t-title">{t.title}</span>
                                <span className="t-time t-context" style={{ color: palette.muted }}>{t.time}</span>
                              </button>
                              <div className="thread-actions">
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
                              New chat
                            </button>
                          </li>
                        </ul>
                      )}
                    </li>
                  )
                })}
              </ul>
              {addingFolder ? (
                <div className="add-folder-form">
                  <input
                    ref={folderInputRef}
                    className="add-folder-input"
                    placeholder="Folder name…"
                    value={folderInput}
                    onChange={(e) => setFolderInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') submitNewFolder()
                      if (e.key === 'Escape') { setFolderInput(''); setAddingFolder(false) }
                    }}
                    style={{ color: palette.ink, borderColor: palette.accent }}
                  />
                  <button className="add-folder-confirm" onClick={submitNewFolder} style={{ color: palette.accent }}>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  </button>
                  <button className="add-folder-cancel" onClick={() => { setFolderInput(''); setAddingFolder(false) }} style={{ color: palette.muted }}>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                  </button>
                </div>
              ) : (
                <button className="add-folder-btn" onClick={() => setAddingFolder(true)} style={{ color: palette.muted }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M12 5v14M5 12h14"/>
                  </svg>
                  Add folder
                </button>
              )}
            </div>
          )}
        </div>

        {/* ── Recents ── */}
        <div className="snav-section">
          <div className="snav-hd" style={{ color: palette.ink, cursor: 'default' }}>
            <span className="snav-icon" style={{ color: palette.muted }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
            </span>
            <span className="snav-label">Recents</span>
          </div>
          <div className="snav-body">
            <ul className="thread-list">
              {recentItems.map(({ thread: t, folderId, folderName }) => (
                <li key={t.id} className="thread-row">
                  <button
                    className={`thread-item ${t.id === activeThreadId && folderId === activeFolderId ? 'active' : ''}`}
                    onClick={() => onSelectThread(folderId, t.id)}
                    style={{ color: palette.ink }}
                    {...threadDragProps(t.id, folderId)}
                  >
                    <span className="t-title">{t.title}</span>
                    {folderName && (
                      <span className="t-context" style={{ color: palette.muted }}>{folderName}</span>
                    )}
                  </button>
                  <div className="thread-actions">
                    <button className="thread-action-btn" title="Delete"
                      onClick={(e) => {
                        e.stopPropagation()
                        folderId === null
                          ? onDeleteGeneralThread(t.id)
                          : onDeleteThread(folderId, t.id)
                      }}
                      style={{ color: palette.muted }}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
                      </svg>
                    </button>
                  </div>
                </li>
              ))}
              {recentItems.length === 0 && (
                <li style={{ padding: '6px 10px', fontSize: 12, color: palette.muted }}>No recent chats.</li>
              )}
            </ul>
          </div>
        </div>
      </div>

      <div className="side-foot" style={{ color: palette.muted, borderColor: 'rgba(0,0,0,0.08)' }}>
        <div className="user-row">
          <div className="avatar" style={{ background: palette.accent, color: palette.bg }}>{initial}</div>
          <div className="user-meta">
            <div style={{ color: palette.ink }}>{user.name || 'Guest'}</div>
            <div>{roleLabel || user.department || 'No department'}{regionLabel ? ' · ' + regionLabel : ''}</div>
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
