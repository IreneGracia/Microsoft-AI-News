'use client'

import { useState, useEffect } from 'react'
import { MOCK_MS_ACCOUNTS, CORPORATE_DOMAIN } from '@/constants/auth'
import type { User, MockAccount } from '@/types'

interface Props {
  open: boolean
  onClose: () => void
  onComplete: (user: User) => void
}

type Step = 'pick' | 'password' | 'stay' | 'done'

export default function MicrosoftSSOModal({ open, onClose, onComplete }: Props) {
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
    if (!/^[^\s@]+@microsoft\.com$/.test(email)) { setPwError('Use your @microsoft.com account.'); return }
    const fallbackName = email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    setAccount({ name: fallbackName, email, department: '', region: '', initial: fallbackName.charAt(0).toLowerCase(), color: '#0078D4' })
    setShowOther(false); setStep('password')
  }

  const submitPassword = () => {
    if (!password || password.length < 4) { setPwError('Enter your password.'); return }
    setPwError(''); setStep('stay')
  }

  const finishStay = (stay: boolean) => {
    setStep('done')
    setTimeout(() => {
      if (!account) return
      onComplete({
        name: account.name, email: account.email,
        department: account.department || 'Engineering',
        region: account.region || 'na',
        signedInAt: Date.now(), sso: true, rememberMe: stay,
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
          <svg width="108" height="23" viewBox="0 0 108 23" aria-label="Microsoft">
            <rect x="0" y="0" width="10" height="10" fill="#F25022" />
            <rect x="11" y="0" width="10" height="10" fill="#7FBA00" />
            <rect x="0" y="11" width="10" height="10" fill="#00A4EF" />
            <rect x="11" y="11" width="10" height="10" fill="#FFB900" />
            <text x="28" y="16" fill="#5E5E5E" style={{ fontFamily: 'Segoe UI, system-ui, sans-serif', fontSize: '13px', fontWeight: 600 }}>Microsoft</text>
          </svg>
        </div>

        {step === 'pick' && !showOther && (
          <>
            <h3 className="ms-h">Pick an account</h3>
            <ul className="ms-accounts">
              {MOCK_MS_ACCOUNTS.map((acc) => (
                <li key={acc.email}>
                  <button className="ms-account" onClick={() => pickAccount(acc)}>
                    <span className="ms-avatar" style={{ background: acc.color }}>{acc.initial.toUpperCase()}</span>
                    <span className="ms-account-meta">
                      <span className="ms-account-name">{acc.name}</span>
                      <span className="ms-account-email">{acc.email}</span>
                    </span>
                    <span className="ms-account-status">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#107C10" strokeWidth="2"><path d="M20 6L9 17l-5-5" /></svg>
                      <span>Signed in</span>
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
            <h3 className="ms-h">Sign in</h3>
            <label className="ms-field">
              <span>Email, phone, or Skype</span>
              <input type="email" value={otherEmail} onChange={(e) => setOtherEmail(e.target.value)}
                placeholder={`someone@${CORPORATE_DOMAIN}`} autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') useOther() }} />
            </label>
            {pwError && <div className="ms-error">{pwError}</div>}
            <p className="ms-note">No account? <a href="#" onClick={(e) => e.preventDefault()}>Create one!</a></p>
            <div className="ms-actions"><button className="ms-primary" onClick={useOther}>Next</button></div>
          </>
        )}

        {step === 'password' && account && (
          <>
            <button className="ms-back" onClick={() => setStep('pick')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
              <span className="ms-back-email">{account.email}</span>
            </button>
            <h3 className="ms-h">Enter password</h3>
            <label className="ms-field">
              <span>Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Password" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') submitPassword() }} />
            </label>
            {pwError && <div className="ms-error">{pwError}</div>}
            <a href="#" className="ms-link" onClick={(e) => e.preventDefault()}>Forgot password?</a>
            <div className="ms-actions"><button className="ms-primary" onClick={submitPassword}>Sign in</button></div>
          </>
        )}

        {step === 'stay' && account && (
          <>
            <h3 className="ms-h">Stay signed in?</h3>
            <p className="ms-body">Do this to reduce the number of times you are asked to sign in.</p>
            <label className="ms-check"><input type="checkbox" /> <span>Don&apos;t show this again</span></label>
            <div className="ms-actions ms-actions-row">
              <button className="ms-secondary" onClick={() => finishStay(false)}>No</button>
              <button className="ms-primary" onClick={() => finishStay(true)}>Yes</button>
            </div>
          </>
        )}

        {step === 'done' && (
          <div className="ms-done">
            <div className="ms-spinner" />
            <p className="ms-body">Signing you in to MAI…</p>
          </div>
        )}

        <div className="ms-foot">
          <a href="#" onClick={(e) => e.preventDefault()}>Terms of use</a>
          <a href="#" onClick={(e) => e.preventDefault()}>Privacy &amp; cookies</a>
        </div>
      </div>
    </div>
  )
}
