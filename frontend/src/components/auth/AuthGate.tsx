'use client'

import { useState } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { writeSession, apiUserToLocal } from '@/lib/session'
import { requestMagicLink, setToken, getMe, devLogin as apiDevLogin } from '@/lib/api'
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

type UIState = 'idle' | 'loading' | 'sent'

export default function AuthGate({ palette, displayFont, newsFont, blur, grain, onAuthed }: Props) {
  const [email, setEmail] = useState('')
  const [uiState, setUiState] = useState<UIState>('idle')
  const [devLink, setDevLink] = useState<string | null>(null)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = email.trim().toLowerCase()
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      return setError('Enter a valid email address.')
    }
    setError('')
    setUiState('loading')
    try {
      const result = await requestMagicLink(trimmed)
      setDevLink(result.dev_link ?? null)
      setUiState('sent')
    } catch {
      setError('Could not send login link. Is the server running?')
      setUiState('idle')
    }
  }

  const handleDevLink = async () => {
    if (!devLink) return
    // Extract token from the dev link and verify it client-side via the backend
    window.location.href = devLink
  }

  const handleDevLogin = async () => {
    setUiState('loading')
    try {
      const data = await apiDevLogin()
      setToken(data.access_token)
      const apiUser = await getMe()
      const u = apiUserToLocal(apiUser)
      writeSession(u)
      onAuthed(u)
    } catch {
      setError('Dev login failed — is the server running?')
      setUiState('idle')
    }
  }

  const reset = () => {
    setUiState('idle')
    setDevLink(null)
    setError('')
    setEmail('')
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
            <p className="auth-line">Tech moves too fast. MAI personalizes the news to your role and region.</p>
            <p className="auth-line">Want to go deeper on any story? Chat with me — I'll pull sources.</p>
          </div>
        </div>

        <div className="auth-card-col">
          <div className="auth-card" style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.08)' }}>

            {uiState === 'sent' ? (
              <>
                <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
                  Check your inbox.
                </h2>
                <p className="auth-sub" style={{ color: palette.muted }}>
                  We sent a login link to <strong>{email}</strong>.<br />
                  Click it to sign in — the link expires in 15 minutes.
                </p>

                {devLink && (
                  <div style={{ marginTop: '1.5rem' }}>
                    <p style={{ color: palette.muted, fontSize: '0.78rem', marginBottom: '0.75rem' }}>
                      Dev mode — no email needed, click directly:
                    </p>
                    <button
                      type="button"
                      className="auth-submit"
                      onClick={handleDevLink}
                      style={{ background: palette.accent, color: '#fff', width: '100%' }}
                    >
                      Open login link →
                    </button>
                  </div>
                )}

                <button
                  type="button"
                  className="auth-link"
                  onClick={reset}
                  style={{ color: palette.muted, marginTop: '1.25rem', display: 'block' }}
                >
                  ← Use a different email
                </button>
              </>
            ) : (
              <>
                <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
                  Sign in.
                </h2>
                <p className="auth-sub" style={{ color: palette.muted }}>
                  Continue with your Google or Microsoft account, or get a passwordless link by email.
                </p>

                {/* OAuth SSO buttons */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1.25rem' }}>
                  <a
                    href={`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'}/auth/login?provider=google`}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem',
                      padding: '0.65rem 1rem', borderRadius: '8px',
                      border: '1px solid rgba(0,0,0,0.18)', background: '#fff',
                      color: '#3c4043', fontSize: '0.88rem', fontWeight: 500,
                      textDecoration: 'none', cursor: 'pointer',
                    }}
                  >
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
                      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
                      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
                      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
                    </svg>
                    Continue with Google
                  </a>

                  <a
                    href={`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'}/auth/login?provider=microsoft`}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem',
                      padding: '0.65rem 1rem', borderRadius: '8px',
                      border: '1px solid rgba(0,0,0,0.18)', background: '#fff',
                      color: '#3c4043', fontSize: '0.88rem', fontWeight: 500,
                      textDecoration: 'none', cursor: 'pointer',
                    }}
                  >
                    <svg width="18" height="18" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <rect x="1" y="1" width="9" height="9" fill="#F25022"/>
                      <rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>
                      <rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>
                      <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
                    </svg>
                    Continue with Microsoft
                  </a>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <div style={{ flex: 1, height: '1px', background: 'rgba(0,0,0,0.1)' }} />
                  <span style={{ color: palette.muted, fontSize: '0.75rem' }}>or continue with email</span>
                  <div style={{ flex: 1, height: '1px', background: 'rgba(0,0,0,0.1)' }} />
                </div>

                <form onSubmit={submit} className="auth-form" noValidate>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Email address</span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      autoComplete="email"
                      autoFocus
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }}
                    />
                  </label>

                  {error && (
                    <div className="auth-error" style={{ color: palette.ink }}>{error}</div>
                  )}

                  <button
                    type="submit"
                    className="auth-submit"
                    disabled={uiState === 'loading'}
                    style={{ background: palette.ink, color: palette.bg }}
                  >
                    {uiState === 'loading' ? 'Sending…' : 'Send login link →'}
                  </button>
                </form>

                <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid rgba(0,0,0,0.07)' }}>
                  <p style={{ color: palette.muted, fontSize: '0.75rem', marginBottom: '0.75rem', textAlign: 'center' }}>
                    Local dev
                  </p>
                  <button
                    type="button"
                    onClick={handleDevLogin}
                    disabled={uiState === 'loading'}
                    style={{
                      width: '100%', padding: '0.6rem 1rem', borderRadius: '6px',
                      border: '1px solid rgba(0,0,0,0.15)', background: 'transparent',
                      color: palette.muted, fontSize: '0.82rem', cursor: 'pointer',
                    }}
                  >
                    Skip → enter as dev user
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
