'use client'

import { useState } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import MicrosoftSSOModal from '@/components/auth/MicrosoftSSOModal'
import GoogleSSOModal from '@/components/auth/GoogleSSOModal'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { CORPORATE_DOMAIN, DEPARTMENTS, REGIONS_AUTH, SIGNUP_ROLES, SIGNUP_DELIVERY } from '@/constants/auth'
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
  const [form, setForm] = useState({ email: '', password: '', confirmPassword: '', name: '', department: '', region: '', role: '', delivery: 'daily' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [ssoOpen, setSsoOpen] = useState(false)
  const [googleOpen, setGoogleOpen] = useState(false)
  const [ssoUser, setSsoUser] = useState<User | null>(null)
  const [ssoPrefs, setSsoPrefs] = useState({ department: '', region: '', role: '', delivery: 'daily' })

  const update = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const validateCorporateEmail = (email: string) => {
    const e = String(email || '').trim().toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return 'Enter a valid email address.'
    return null
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (mode === 'signin') {
      if (!form.password || form.password.length < 6) return setError('Password must be at least 6 characters.')
      const emailErr = validateCorporateEmail(form.email)
      if (emailErr) return setError(emailErr)
    } else {
      if (!form.name.trim()) return setError('Please enter your name.')
      const emailErr = validateCorporateEmail(form.email)
      if (emailErr) return setError(emailErr)
      if (!form.password || form.password.length < 6) return setError('Password must be at least 6 characters.')
      if (form.password !== form.confirmPassword) return setError('Passwords do not match.')
      if (!form.role) return setError('Please choose your role.')
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
        role: form.role || 'engineer',
        delivery: [form.delivery || 'daily'],
        signedInAt: Date.now(),
      }
      writeSession(user)
      setLoading(false)
      onAuthed(user)
    }, 500)
  }

  const completeSso = (user: User) => {
    setSsoOpen(false)
    setGoogleOpen(false)
    if (mode === 'signup') {
      setSsoPrefs({ department: '', region: '', role: '', delivery: 'daily' })
      setSsoUser(user)
    } else {
      writeSession(user)
      onAuthed(user)
    }
  }

  const finishSsoPrefs = () => {
    if (!ssoPrefs.role) return setError('Please choose your role.')
    if (!ssoPrefs.region) return setError('Please choose your region.')
    setError('')
    const final: User = {
      ...ssoUser!,
      department: ssoPrefs.department || ssoPrefs.role,
      region: ssoPrefs.region,
      role: ssoPrefs.role,
      delivery: [ssoPrefs.delivery || 'daily'],
    }
    writeSession(final)
    setSsoUser(null)
    onAuthed(final)
  }

  if (ssoUser) {
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
              <p className="auth-line">Almost there, {ssoUser.name.split(' ')[0]}. Just a couple of details so MAI knows what matters to you.</p>
            </div>
          </div>
          <div className="auth-card-col">
            <div className="auth-card" style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.08)' }}>
              <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>Personalize your feed.</h2>
              <p className="auth-sub" style={{ color: palette.muted }}>Tell MAI where you work and where you are.</p>
              <div className="auth-form">
                <div className="auth-field">
                  <span style={{ color: palette.muted }}>Your angle on tech</span>
                  <div className="auth-region-grid">
                    {SIGNUP_ROLES.map((r) => {
                      const on = ssoPrefs.role === r.id
                      return (
                        <button type="button" key={r.id} className={`auth-region ${on ? 'on' : ''}`}
                          onClick={() => setSsoPrefs((p) => ({ ...p, role: r.id }))}
                          style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                          {r.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div className="auth-field">
                  <span style={{ color: palette.muted }}>Region</span>
                  <div className="auth-region-grid">
                    {REGIONS_AUTH.map((r) => {
                      const on = ssoPrefs.region === r.id
                      return (
                        <button type="button" key={r.id} className={`auth-region ${on ? 'on' : ''}`}
                          onClick={() => setSsoPrefs((p) => ({ ...p, region: r.id }))}
                          style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                          {r.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div className="auth-field">
                  <span style={{ color: palette.muted }}>How often do you want your briefing?</span>
                  <div className="auth-region-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                    {SIGNUP_DELIVERY.map((d) => {
                      const on = ssoPrefs.delivery === d.id
                      return (
                        <button type="button" key={d.id} className={`auth-region ${on ? 'on' : ''}`}
                          onClick={() => setSsoPrefs((p) => ({ ...p, delivery: d.id }))}
                          style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                          {d.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
                {error && <div className="auth-error" style={{ color: palette.ink }}>{error}</div>}
                <button type="button" className="auth-submit" onClick={finishSsoPrefs}
                  style={{ background: palette.ink, color: palette.bg }}>
                  Start reading →
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
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

            {/* SSO buttons — signup shows both, signin shows only Microsoft */}
            <div className="auth-sso-stack">
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

              <button type="button" className="auth-sso" onClick={() => setGoogleOpen(true)} disabled={loading}
                style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)', background: 'rgba(255,253,247,0.6)' }}>
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                <span>Continue with Google</span>
              </button>
            </div>

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
                <span className="auth-hint" style={{ color: palette.muted }}>
                  {mode === 'signup'
                    ? 'Use your Microsoft account (outlook.com, hotmail.com, or work account).'
                    : `Must be your @${CORPORATE_DOMAIN} address.`}
                </span>
              </label>

              {mode === 'signup' && (
                <>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Password</span>
                    <input type="password" value={form.password} onChange={(e) => update('password', e.target.value)}
                      placeholder="••••••••" autoComplete="new-password"
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
                  </label>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Confirm password</span>
                    <input type="password" value={form.confirmPassword} onChange={(e) => update('confirmPassword', e.target.value)}
                      placeholder="••••••••" autoComplete="new-password"
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
                  </label>
                  <div className="auth-field">
                    <span style={{ color: palette.muted }}>Your angle on tech</span>
                    <div className="auth-region-grid">
                      {SIGNUP_ROLES.map((r) => {
                        const on = form.role === r.id
                        return (
                          <button type="button" key={r.id} className={`auth-region ${on ? 'on' : ''}`}
                            onClick={() => update('role', r.id)}
                            style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                            {r.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Department</span>
                    <select value={form.department} onChange={(e) => update('department', e.target.value)}
                      style={{ color: form.department ? palette.ink : 'rgba(0,0,0,0.38)', borderColor: 'rgba(0,0,0,0.16)' }}>
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
                  <div className="auth-field">
                    <span style={{ color: palette.muted }}>How often do you want your briefing?</span>
                    <div className="auth-region-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                      {SIGNUP_DELIVERY.map((d) => {
                        const on = form.delivery === d.id
                        return (
                          <button type="button" key={d.id} className={`auth-region ${on ? 'on' : ''}`}
                            onClick={() => update('delivery', d.id)}
                            style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                            {d.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </>
              )}

              {mode === 'signin' && (
                <>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Password</span>
                    <input type="password" value={form.password} onChange={(e) => update('password', e.target.value)}
                      placeholder="••••••••" autoComplete="current-password"
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
                  </label>
                  <div className="auth-row-between">
                    <label className="auth-check" style={{ color: palette.muted }}>
                      <input type="checkbox" /> Remember me
                    </label>
                    <button type="button" className="auth-link" style={{ color: palette.accent }}>Forgot password?</button>
                  </div>
                </>
              )}

              {error && <div className="auth-error" style={{ color: palette.ink }}>{error}</div>}

              <button type="submit" className={`auth-submit ${mode === 'signup' ? 'auth-submit-signup' : ''}`}
                disabled={loading} style={{ background: palette.ink, color: palette.bg }}>
                {loading
                  ? (mode === 'signup' ? 'Creating account…' : 'Signing in…')
                  : mode === 'signin' ? 'Sign in' : 'Create account →'}
              </button>
            </form>

            <p className="auth-meta" style={{ color: palette.muted }}>
              By continuing you agree to MAI&apos;s terms and Microsoft&apos;s internal data-handling policies. We never send breaking-news alerts you haven&apos;t asked for.
            </p>
          </div>
        </div>
      </div>

      <MicrosoftSSOModal open={ssoOpen} onClose={() => setSsoOpen(false)} onComplete={completeSso} />
      <GoogleSSOModal open={googleOpen} onClose={() => setGoogleOpen(false)} onComplete={completeSso} />
    </div>
  )
}
