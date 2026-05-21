'use client'

import { useState } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import MicrosoftSSOModal from '@/components/auth/MicrosoftSSOModal'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { CORPORATE_DOMAIN, DEPARTMENTS, REGIONS_AUTH } from '@/constants/auth'
import { writeSession } from '@/lib/session'
import type { Palette, User } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  blur: number
  grain: number
  mode: 'signin' | 'signup'
  setMode: (m: 'signin' | 'signup') => void
  onAuthed: (user: User) => void
}

export default function AuthGate({ palette, displayFont, newsFont, blur, grain, mode, setMode, onAuthed }: Props) {
  const [form, setForm] = useState({ email: '', password: '', name: '', department: '', region: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [ssoOpen, setSsoOpen] = useState(false)

  const update = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const validateCorporateEmail = (email: string) => {
    const e = String(email || '').trim().toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return 'Enter a valid email address.'
    if (!e.endsWith('@' + CORPORATE_DOMAIN)) return `Use your corporate email (@${CORPORATE_DOMAIN}).`
    return null
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const emailErr = validateCorporateEmail(form.email)
    if (emailErr) return setError(emailErr)
    if (!form.password || form.password.length < 6) return setError('Password must be at least 6 characters.')
    if (mode === 'signup') {
      if (!form.name.trim()) return setError('Please enter your name.')
      if (!form.department) return setError('Please choose your department.')
      if (!form.region) return setError('Please choose your region.')
    }
    setLoading(true)
    setTimeout(() => {
      const fallbackName = form.email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
      const user: User = {
        name: form.name.trim() || fallbackName,
        email: form.email.trim().toLowerCase(),
        department: form.department || 'Engineering',
        region: form.region || 'eu',
        signedInAt: Date.now(),
      }
      writeSession(user)
      setLoading(false)
      onAuthed(user)
    }, 500)
  }

  const completeSso = (user: User) => {
    writeSession(user)
    setSsoOpen(false)
    onAuthed(user)
  }

  return (
    <div className="auth-shell" style={{ color: palette.ink, fontFamily: "'Inter Tight', system-ui, sans-serif" }}>
      <Backdrop palette={palette} blur={blur} grain={grain} />

      <div className="auth-grid">
        <div className="auth-hero">
          <div className="brand auth-brand">
            <MaiMark palette={palette} size={44} />
            <Wordmark palette={palette} displayFont={displayFont} newsFont={newsFont} size={38} />
          </div>
          <h1 className="auth-headline" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
            Tech news,<br /><em>made yours.</em>
          </h1>
          <div className="auth-bullets" style={{ color: palette.muted }}>
            <p className="auth-line">Tech moves too fast. MAI personalizes the news to your preferences and sends it your way.</p>
            <p className="auth-line">Want to know more? Chat with me — I&apos;ll dig deeper, with sources.</p>
          </div>
        </div>

        <div className="auth-card-col">
          <div className="auth-card" style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.08)' }}>
            <div className="auth-tabs">
              <button type="button" className={`auth-tab ${mode === 'signin' ? 'on' : ''}`}
                onClick={() => { setMode('signin'); setError('') }}
                style={mode === 'signin' ? { color: palette.ink, borderBottomColor: palette.ink } : { color: palette.muted, borderBottomColor: 'transparent' }}>
                Sign in
              </button>
              <button type="button" className={`auth-tab ${mode === 'signup' ? 'on' : ''}`}
                onClick={() => { setMode('signup'); setError('') }}
                style={mode === 'signup' ? { color: palette.ink, borderBottomColor: palette.ink } : { color: palette.muted, borderBottomColor: 'transparent' }}>
                Create account
              </button>
            </div>

            <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
              {mode === 'signin' ? 'Welcome back.' : (
                <>Get your first <span style={{ fontFamily: NEWS_FONTS[newsFont], fontStyle: 'italic', fontWeight: 600, color: palette.accent }}>briefing</span>.</>
              )}
            </h2>
            <p className="auth-sub" style={{ color: palette.muted }}>
              {mode === 'signin' ? 'Use your Microsoft corporate account to continue.' : 'A few quiet details. Then MAI shapes the news around you.'}
            </p>

            <button type="button" className="auth-sso" onClick={() => setSsoOpen(true)} disabled={loading}
              style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)', background: 'rgba(255,253,247,0.6)' }}>
              <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
                <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
              </svg>
              <span>Continue with Microsoft</span>
            </button>

            <div className="auth-divider" style={{ color: palette.muted }}>
              <span className="auth-divider-line" />
              <span>or</span>
              <span className="auth-divider-line" />
            </div>

            <form onSubmit={submit} className="auth-form" noValidate>
              {mode === 'signup' && (
                <label className="auth-field">
                  <span style={{ color: palette.muted }}>Full name</span>
                  <input type="text" value={form.name} onChange={(e) => update('name', e.target.value)}
                    placeholder="Eve Sandoval" autoComplete="name"
                    style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
                </label>
              )}

              <label className="auth-field">
                <span style={{ color: palette.muted }}>Corporate email</span>
                <input type="email" value={form.email} onChange={(e) => update('email', e.target.value)}
                  placeholder={`you@${CORPORATE_DOMAIN}`} autoComplete="email"
                  style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
                <span className="auth-hint" style={{ color: palette.muted }}>Must be your @{CORPORATE_DOMAIN} address.</span>
              </label>

              {mode === 'signup' && (
                <>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Department</span>
                    <select value={form.department} onChange={(e) => update('department', e.target.value)}
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }}>
                      <option value="">Choose your department…</option>
                      {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </label>
                  <div className="auth-field">
                    <span style={{ color: palette.muted }}>Region</span>
                    <div className="auth-region-grid">
                      {REGIONS_AUTH.map((r) => {
                        const on = form.region === r.id
                        return (
                          <button type="button" key={r.id} className={`auth-region ${on ? 'on' : ''}`}
                            onClick={() => update('region', r.id)}
                            style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                            {r.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </>
              )}

              <label className="auth-field">
                <span style={{ color: palette.muted }}>Password</span>
                <input type="password" value={form.password} onChange={(e) => update('password', e.target.value)}
                  placeholder="••••••••" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                  style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
              </label>

              {mode === 'signin' && (
                <div className="auth-row-between">
                  <label className="auth-check" style={{ color: palette.muted }}>
                    <input type="checkbox" /> Remember me
                  </label>
                  <button type="button" className="auth-link" style={{ color: palette.accent }}>Forgot password?</button>
                </div>
              )}

              {error && <div className="auth-error" style={{ color: palette.ink }}>{error}</div>}

              <button type="submit" className="auth-submit" disabled={loading}
                style={{ background: palette.ink, color: palette.bg }}>
                {loading ? 'Signing in…' : mode === 'signin' ? 'Sign in' : 'Create account'}
              </button>
            </form>

            <p className="auth-meta" style={{ color: palette.muted }}>
              By continuing you agree to MAI&apos;s terms and Microsoft&apos;s internal data-handling policies. We never send breaking-news alerts you haven&apos;t asked for.
            </p>
          </div>
        </div>
      </div>

      <MicrosoftSSOModal open={ssoOpen} onClose={() => setSsoOpen(false)} onComplete={completeSso} />
    </div>
  )
}
