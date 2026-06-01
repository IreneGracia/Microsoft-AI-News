'use client'

import { useState } from 'react'
import { FONTS } from '@/constants/fonts'
import type { ForumPost, Palette, User } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  posts: ForumPost[]
  user: User
  onAddPost: (post: ForumPost) => void
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onLike: (id: string) => void
}

export default function Forum({ palette, displayFont, posts, user, onAddPost, onApprove, onReject, onLike }: Props) {
  const [modMode, setModMode] = useState(false)
  const [composing, setComposing] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const approved = posts.filter((p) => p.status === 'approved')
  const pending = posts.filter((p) => p.status === 'pending')

  const handleSubmit = () => {
    if (!title.trim() || !content.trim()) return
    onAddPost({
      id: 'fp' + Date.now(),
      authorName: user.name || 'Anonymous',
      title: title.trim(),
      content: content.trim(),
      status: 'pending',
      createdAt: new Date().toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }),
      likes: 0,
      likedByMe: false,
    })
    setTitle('')
    setContent('')
    setComposing(false)
  }

  return (
    <div className="forum-view">
      {/* Header */}
      <div className="forum-header">
        <div className="saved-eyebrow" style={{ color: palette.muted }}>Community</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <h2 className="saved-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
            Forum
          </h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="forum-mod-btn" onClick={() => setModMode((v) => !v)}
              style={{ color: modMode ? palette.bg : palette.muted, background: modMode ? palette.ink : 'transparent', borderColor: modMode ? palette.ink : 'rgba(0,0,0,0.15)' }}>
              {modMode ? 'Exit moderation' : 'Moderate'}
            </button>
            <button className="forum-new-btn" onClick={() => setComposing(true)}
              style={{ background: palette.ink, color: palette.bg }}>
              + New post
            </button>
          </div>
        </div>
        <p className="saved-sub" style={{ color: palette.muted }}>
          Ask questions, share opinions and discuss with your team. Posts are reviewed before publishing.
        </p>
      </div>

      {/* Compose form */}
      {composing && (
        <div className="forum-compose" style={{ borderColor: 'rgba(0,0,0,0.08)', background: palette.cardBg }}>
          <div className="folder-form-label" style={{ color: palette.muted }}>New post</div>
          <input
            className="folder-form-input" placeholder="Title…"
            value={title} onChange={(e) => setTitle(e.target.value)}
            style={{ color: palette.ink }} autoFocus
          />
          <textarea
            className="forum-textarea" placeholder="Share your question or opinion…"
            value={content} onChange={(e) => setContent(e.target.value)}
            style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.8)' }}
            rows={4}
          />
          <div className="folder-form-actions">
            <button className="folder-form-cancel" onClick={() => setComposing(false)} style={{ color: palette.muted }}>Cancel</button>
            <button className="folder-form-save" onClick={handleSubmit}
              disabled={!title.trim() || !content.trim()}
              style={{ background: palette.ink, color: palette.bg }}>
              Submit for review
            </button>
          </div>
        </div>
      )}

      {/* Pending posts (moderation mode) */}
      {modMode && pending.length > 0 && (
        <div className="forum-section">
          <div className="forum-section-label" style={{ color: '#b02020' }}>
            Pending review ({pending.length})
          </div>
          {pending.map((p) => (
            <ForumCard key={p.id} post={p} palette={palette} displayFont={displayFont}
              modMode={modMode} onLike={onLike} onApprove={onApprove} onReject={onReject} />
          ))}
        </div>
      )}

      {modMode && pending.length === 0 && (
        <div className="forum-section">
          <div className="forum-section-label" style={{ color: palette.muted }}>Pending review</div>
          <p style={{ color: palette.muted, fontSize: 13, padding: '8px 0' }}>No posts pending review.</p>
        </div>
      )}

      {/* Approved posts */}
      <div className="forum-section">
        {approved.length === 0 ? (
          <div className="saved-empty" style={{ color: palette.muted }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <p>No posts yet. Be the first to share something.</p>
          </div>
        ) : (
          approved.map((p) => (
            <ForumCard key={p.id} post={p} palette={palette} displayFont={displayFont}
              modMode={modMode} onLike={onLike} onApprove={onApprove} onReject={onReject} />
          ))
        )}
      </div>
    </div>
  )
}

function ForumCard({ post, palette, displayFont, modMode, onLike, onApprove, onReject }: {
  post: ForumPost; palette: Palette; displayFont: string
  modMode: boolean; onLike: (id: string) => void
  onApprove: (id: string) => void; onReject: (id: string) => void
}) {
  return (
    <div className="forum-card" style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.07)' }}>
      <div className="forum-card-meta" style={{ color: palette.muted }}>
        <span className="forum-card-author">{post.authorName}</span>
        <span>·</span>
        <span>{post.createdAt}</span>
        {post.status === 'pending' && (
          <span className="forum-badge-pending">Pending</span>
        )}
      </div>
      <h3 className="forum-card-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
        {post.title}
      </h3>
      <p className="forum-card-content" style={{ color: palette.muted }}>{post.content}</p>
      <div className="forum-card-foot">
        <button className="forum-like-btn" onClick={() => onLike(post.id)}
          style={{ color: post.likedByMe ? palette.accent : palette.muted }}>
          <svg width="13" height="13" viewBox="0 0 24 24"
            fill={post.likedByMe ? 'currentColor' : 'none'}
            stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
          {post.likes > 0 && <span>{post.likes}</span>}
        </button>
        {modMode && post.status === 'pending' && (
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            <button className="forum-reject-btn" onClick={() => onReject(post.id)}
              style={{ color: '#b02020', borderColor: 'rgba(180,0,0,0.2)' }}>
              Reject
            </button>
            <button className="forum-approve-btn" onClick={() => onApprove(post.id)}
              style={{ background: '#1a7a50', color: '#fff' }}>
              Approve
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
