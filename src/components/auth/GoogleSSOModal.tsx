'use client'

import { useState, useEffect } from 'react'
import type { User, MockAccount } from '@/types'

const MOCK_GOOGLE_ACCOUNTS: MockAccount[] = [
  { name: 'Eve Sandoval',  email: 'eve.sandoval@gmail.com',   department: 'Cloud + AI', region: 'eu',    initial: 'e', color: '#4285F4' },
  { name: 'Daniel Kim',    email: 'daniel.kim@gmail.com',     department: 'Azure',      region: 'na',    initial: 'd', color: '#34A853' },
  { name: 'Priya Iyer',    email: 'priya.iyer@gmail.com',     department: 'Research',   region: 'india', initial: 'p', color: '#EA4335' },
]

interface Props {
  open: boolean
  onClose: () => void
  onComplete: (user: User) => void
}

type Step = 'pick' | 'password' | 'done'

export default function GoogleSSOModal({ open, onClose, onComplete }: Props) {
  const [step, setStep] = useState<Step>('pick')
  const [account, setAccount] = useState<MockAccount | null>(null)
  const [password, setPassword] = useState('')
  const [pwError, setPwError] = useState('')
  const [otherEmail, setOtherEmail] = useState('')
  const [showOther, setShowOther] = useState(false)

  useEffect(() => {
    if (open) {
      setStep('pick'); setAccount(null); setPassword('')
      setPwError(''); setOtherEmail(''); setShowOther(false)
    }
  }, [open])

  if (!open) return null

  const pickAccount = (acc: MockAccount) => { setAccount(acc); setStep('password') }

  const useOther = () => {
    const email = otherEmail.trim().toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setPwError('Enter a valid email address.'); return }
    const fallbackName = email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    setAccount({ name: fallbackName, email, department: '', region: '', initial: fallbackName.charAt(0).toLowerCase(), color: '#4285F4' })
    setShowOther(false); setStep('password')
  }

  const submitPassword = () => {
    if (!password || password.length < 4) { setPwError('Enter your password.'); return }
    setPwError('')
    setStep('done')
    setTimeout(() => {
      if (!account) return
      onComplete({
        name: account.name, email: account.email,
        department: account.department || 'Engineering',
        region: account.region || 'na',
        signedInAt: Date.now(), sso: true, rememberMe: true,
      })
    }, 700)
  }

  return (
    <div className="ms-overlay" onClick={onClose}>
      <div className="ms-card" onClick={(e) => e.stopPropagation()}>
        <button className="ms-close" onClick={onClose} aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>

        <div className="ms-logo-row">
          <svg width="74" height="24" viewBox="0 0 74 24" aria-label="Google">
            <path d="M9.24 8.19v2.46h5.88c-.18 1.38-.64 2.37-1.34 3.06-.86.86-2.2 1.8-4.54 1.8-3.62 0-6.45-2.92-6.45-6.54s2.83-6.54 6.45-6.54c1.95 0 3.38.77 4.43 1.76L15.4 2.5C13.97 1.14 12.05.24 9.24.24 4.28.24.34 4.18.34 9.14s3.94 8.9 8.9 8.9c2.61 0 4.57-.86 6.1-2.44 1.58-1.58 2.06-3.8 2.06-5.59 0-.55-.04-1.06-.13-1.48H9.24z" fill="#4285F4"/>
            <path d="M25 6.19c-3.21 0-5.83 2.44-5.83 5.81 0 3.34 2.62 5.81 5.83 5.81s5.83-2.46 5.83-5.81c0-3.37-2.62-5.81-5.83-5.81zm0 9.33c-1.76 0-3.28-1.45-3.28-3.52 0-2.09 1.52-3.52 3.28-3.52s3.28 1.43 3.28 3.52c0 2.07-1.52 3.52-3.28 3.52z" fill="#EA4335"/>
            <path d="M53.58 7.49h-.09c-.57-.68-1.67-1.3-3.06-1.3C47.53 6.19 45 8.72 45 12c0 3.26 2.53 5.81 5.43 5.81 1.39 0 2.49-.62 3.06-1.32h.09v.81c0 2.28-1.22 3.5-3.18 3.5-1.6 0-2.6-1.15-3.01-2.12l-2.22.92c.66 1.58 2.39 3.51 5.23 3.51 3.04 0 5.61-1.79 5.61-6.15V6.49h-2.43v1zm-2.93 8.03c-1.76 0-3.24-1.48-3.24-3.52 0-2.06 1.48-3.52 3.24-3.52 1.74 0 3.18 1.48 3.18 3.54 0 2.04-1.44 3.5-3.18 3.5z" fill="#4285F4"/>
            <path d="M38 6.19c-3.21 0-5.83 2.44-5.83 5.81 0 3.34 2.62 5.81 5.83 5.81s5.83-2.46 5.83-5.81c0-3.37-2.62-5.81-5.83-5.81zm0 9.33c-1.76 0-3.28-1.45-3.28-3.52 0-2.09 1.52-3.52 3.28-3.52s3.28 1.43 3.28 3.52c0 2.07-1.52 3.52-3.28 3.52z" fill="#FBBC05"/>
            <path d="M58.37 1.02h2.54v16.76h-2.54z" fill="#34A853"/>
            <path d="M68.37 15.52c-1.3 0-2.22-.59-2.82-1.76l7.77-3.21-.26-.66c-.48-1.3-1.96-3.7-4.97-3.7-2.99 0-5.48 2.35-5.48 5.81 0 3.26 2.46 5.81 5.76 5.81 2.66 0 4.2-1.63 4.84-2.57l-1.98-1.32c-.66.96-1.56 1.6-2.86 1.6zm-.18-7.15c1.03 0 1.91.53 2.2 1.28l-5.25 2.17c0-2.44 1.73-3.45 3.05-3.45z" fill="#EA4335"/>
          </svg>
        </div>

        {step === 'pick' && !showOther && (
          <>
            <h3 className="ms-h">Choose an account</h3>
            <ul className="ms-accounts">
              {MOCK_GOOGLE_ACCOUNTS.map((acc) => (
                <li key={acc.email}>
                  <button className="ms-account" onClick={() => pickAccount(acc)}>
                    <span className="ms-avatar" style={{ background: acc.color }}>{acc.initial.toUpperCase()}</span>
                    <span className="ms-account-meta">
                      <span className="ms-account-name">{acc.name}</span>
                      <span className="ms-account-email">{acc.email}</span>
                    </span>
                  </button>
                </li>
              ))}
              <li>
                <button className="ms-account ms-other" onClick={() => setShowOther(true)}>
                  <span className="ms-avatar ms-avatar-plus">+</span>
                  <span className="ms-account-name">Use another account</span>
                </button>
              </li>
            </ul>
          </>
        )}

        {step === 'pick' && showOther && (
          <>
            <button className="ms-back" onClick={() => { setShowOther(false); setPwError('') }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
            </button>
            <h3 className="ms-h">Sign in with Google</h3>
            <label className="ms-field">
              <span>Email or phone</span>
              <input type="email" value={otherEmail} onChange={(e) => setOtherEmail(e.target.value)}
                placeholder="you@gmail.com" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') useOther() }} />
            </label>
            {pwError && <div className="ms-error">{pwError}</div>}
            <div className="ms-actions"><button className="ms-primary" style={{ background: '#4285F4' }} onClick={useOther}>Next</button></div>
          </>
        )}

        {step === 'password' && account && (
          <>
            <button className="ms-back" onClick={() => setStep('pick')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
              <span className="ms-back-email">{account.email}</span>
            </button>
            <h3 className="ms-h">Enter your password</h3>
            <label className="ms-field">
              <span>Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Password" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') submitPassword() }} />
            </label>
            {pwError && <div className="ms-error">{pwError}</div>}
            <a href="#" className="ms-link" style={{ color: '#4285F4' }} onClick={(e) => e.preventDefault()}>Forgot password?</a>
            <div className="ms-actions"><button className="ms-primary" style={{ background: '#4285F4' }} onClick={submitPassword}>Next</button></div>
          </>
        )}

        {step === 'done' && (
          <div className="ms-done">
            <div className="ms-spinner" style={{ borderTopColor: '#4285F4' }} />
            <p className="ms-body">Signing you in to MAI…</p>
          </div>
        )}

        <div className="ms-foot">
          <a href="#" onClick={(e) => e.preventDefault()}>Privacy</a>
          <a href="#" onClick={(e) => e.preventDefault()}>Terms</a>
        </div>
      </div>
    </div>
  )
}
