'use client'

import { useState, useRef, useEffect } from 'react'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { REGIONS_AUTH } from '@/constants/auth'
import { PREF_ROLES, TOPIC_GROUPS, PREF_DEPTHS, PREF_DELIVERY, PREF_TONES } from '@/constants/preferences'
import { grainSvg } from '@/lib/grain'
import { putPreferences } from '@/lib/api'
import type { NewsFolder, Palette, Prefs, User } from '@/types'

const topicMap = Object.fromEntries(
  TOPIC_GROUPS.flatMap((g) => g.items.map((i) => [i.id, i.label]))
)

interface Props {
  open: boolean
  onClose: () => void
  palette: Palette
  displayFont: string
  newsFont: string
  prefs: Prefs
  setPrefs: (p: Prefs) => void
  onSave: () => void
  user: User
  folderMode?: boolean
  onCreateFolder?: (folder: NewsFolder) => void
}

const STEPS = ['Role', 'Region', 'Topics', 'Depth', 'Delivery', 'Voice']

export default function PrefsDeck({ open, onClose, palette, displayFont, newsFont, prefs, setPrefs, onSave, user, folderMode = false, onCreateFolder }: Props) {
  const [step, setStep] = useState(0)
  const [showSummary, setShowSummary] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (open) { setStep(0); setShowSummary(false) } }, [open])
  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = 0 }, [step])

  const buildFolder = (): NewsFolder => {
    const topics = prefs.topics || []
    const labels = topics.slice(0, 3).map((t) => topicMap[t] || t)
    const name = labels.length === 0 ? 'Mi folder'
      : topics.length > 3 ? labels.slice(0, 2).join(' · ') + ` +${topics.length - 2}`
      : labels.join(' · ')
    const freq = (prefs.delivery?.[0] as NewsFolder['frequency']) || 'daily'
    return { id: 'f' + Date.now(), name, topics, frequency: freq, keywords: [], threads: [] }
  }

  const handleFinish = async () => {
    // 'breaking' is UI-only — map to 'daily' for the API
    const apiFrequency = prefs.delivery?.[0] === 'breaking'
      ? 'daily'
      : (prefs.delivery?.[0] as 'daily' | 'weekdays' | 'weekly') ?? 'weekly'
    try {
      await putPreferences({
        topics: prefs.topics ?? [],
        regions: prefs.region ? [prefs.region] : [],
        role: prefs.role ?? null,
        frequency: apiFrequency,
        length: (prefs.depth as 'short' | 'standard' | 'deep') ?? 'standard',
        tone: (prefs.tone as 'technical' | 'business' | 'executive') ?? 'technical',
        newsletter_consent: prefs.newsletterConsent ?? false,
      })
    } catch { /* best-effort — prefs live in local state even if API is down */ }

    if (folderMode) {
      setShowSummary(true)
    } else {
      onSave()  // closes the modal and triggers dashboard re-fetch via prefs.topics
    }
  }

  const confirmCreateFolder = () => {
    onCreateFolder?.(buildFolder())
    setShowSummary(false)
  }

  if (!open) return null

  const toggleArr = (key: keyof Prefs, id: string) => {
    const arr = (prefs[key] as string[]) || []
    setPrefs({ ...prefs, [key]: arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id] })
  }
  const setOne = (key: keyof Prefs, id: string) => setPrefs({ ...prefs, [key]: id })

  const pickRole = (roleId: string) => {
    const role = PREF_ROLES.find((r) => r.id === roleId)
    setPrefs({ ...prefs, role: roleId, depth: prefs.depth || role?.defaultDepth })
  }

  return (
    <div className="prefs-overlay" onClick={onClose}>
      <div className="prefs-deck" onClick={(e) => e.stopPropagation()} style={{ background: palette.bg, color: palette.ink, borderColor: 'rgba(0,0,0,0.08)' }}>
        <div className="prefs-grain" style={{ backgroundImage: `url("${grainSvg(0.12)}")` }} />
        <button className="prefs-close" onClick={onClose} aria-label="Close" style={{ color: palette.muted }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>

        <header className="prefs-head">
          <div className="prefs-eyebrow" style={{ color: palette.muted }}>
            {folderMode ? 'Nuevo folder' : 'Your reading preferences'}
          </div>
          <h2 className="prefs-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
            {folderMode
              ? <>Configura tu <span className="prefs-news" style={{ fontFamily: NEWS_FONTS[newsFont], color: palette.accent }}>folder</span></>
              : <>Tune your <span className="prefs-news" style={{ fontFamily: NEWS_FONTS[newsFont], color: palette.accent }}>news</span></>}
          </h2>
          <p className="prefs-sub" style={{ color: palette.muted }}>
            {folderMode
              ? 'Elige los temas y la frecuencia. El nombre se genera automáticamente.'
              : 'A few quiet choices. MAI uses them to shape every briefing.'}
          </p>

          <div className="prefs-stepper">
            {STEPS.map((s, i) => (
              <button key={s} className={`prefs-step ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
                onClick={() => setStep(i)} style={{ color: i === step ? palette.ink : palette.muted }}>
                <span className="prefs-step-num" style={{ borderColor: i === step ? palette.ink : 'rgba(0,0,0,0.2)' }}>{String(i + 1).padStart(2, '0')}</span>
                <span>{s}</span>
              </button>
            ))}
          </div>
        </header>

        <div className="prefs-body" ref={bodyRef}>
          {step === 0 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>What&apos;s your angle on tech?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>I&apos;ll match content, depth, and tone to your role. You can override anything later.</div>
              <div className="prefs-radio-col">
                {PREF_ROLES.map((r) => {
                  const on = prefs.role === r.id
                  return (
                    <button key={r.id} className={`prefs-radio ${on ? 'on' : ''}`} onClick={() => pickRole(r.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : 'rgba(0,0,0,0.1)', background: on ? palette.cardBg : 'rgba(255,253,247,0.4)' }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : 'transparent' }} />
                      <div>
                        <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{r.label}</div>
                        <div className="prefs-radio-note" style={{ color: palette.muted }}>{r.note}</div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>Which region matters most to you?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Pre-filled from your signup. Change anytime.</div>
              <div className="prefs-region-grid">
                {REGIONS_AUTH.map((r) => {
                  const on = (prefs.region || user.region) === r.id
                  return (
                    <button key={r.id} className={`prefs-region ${on ? 'on' : ''}`} onClick={() => setOne('region', r.id)}
                      style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                      {r.label}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>What corners of tech matter to you?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Pick as many as you like. You can change this anytime.</div>
              {TOPIC_GROUPS.map((group) => (
                <div key={group.id} className="prefs-group">
                  <div className="prefs-group-head">
                    <div className="prefs-group-label" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>{group.label}</div>
                    <div className="prefs-group-note" style={{ color: palette.muted }}>{group.note}</div>
                  </div>
                  <div className="prefs-chips">
                    {group.items.map((t) => {
                      const on = (prefs.topics || []).includes(t.id)
                      return (
                        <button key={t.id} className={`prefs-chip ${on ? 'on' : ''}`} onClick={() => toggleArr('topics', t.id)}
                          style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.55)' }}>
                          <span className="prefs-chip-mark">{on ? '✓' : '+'}</span>
                          <span>{t.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {step === 3 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>How deep should I go?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Pre-set from your role. You can always ask for more or less in chat.</div>
              <div className="prefs-radio-col">
                {PREF_DEPTHS.map((d) => {
                  const on = prefs.depth === d.id
                  return (
                    <button key={d.id} className={`prefs-radio ${on ? 'on' : ''}`} onClick={() => setOne('depth', d.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : 'rgba(0,0,0,0.1)', background: on ? palette.cardBg : 'rgba(255,253,247,0.4)' }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : 'transparent' }} />
                      <div>
                        <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{d.label}</div>
                        <div className="prefs-radio-note" style={{ color: palette.muted }}>{d.note}</div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>When should I bring you the news?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>No streaks. No notifications you didn&apos;t ask for.</div>
              <div className="prefs-radio-col">
                {PREF_DELIVERY.map((c) => {
                  const on = prefs.delivery?.[0] === c.id
                  return (
                    <button key={c.id} className={`prefs-radio ${on ? 'on' : ''}`}
                      onClick={() => setPrefs({ ...prefs, delivery: [c.id] })}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : 'rgba(0,0,0,0.1)', background: on ? palette.cardBg : 'rgba(255,253,247,0.4)' }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : 'transparent' }} />
                      <div style={{ flex: 1 }}>
                        <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{c.label}</div>
                        <div className="prefs-radio-note" style={{ color: palette.muted }}>{c.note}</div>
                      </div>
                    </button>
                  )
                })}
              </div>
              {prefs.delivery?.[0] === 'breaking' && (
                <div className="prefs-keywords">
                  <label className="prefs-keywords-label" style={{ color: palette.muted }}>Keywords for breaking-news alerts</label>
                  <input type="text" className="prefs-keywords-input"
                    placeholder="GPT-5, Copilot, EU AI Act…"
                    value={prefs.keywords || ''}
                    onChange={(e) => setPrefs({ ...prefs, keywords: e.target.value })}
                    style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
                  <p className="prefs-keywords-hint" style={{ color: palette.muted }}>Comma-separated. I&apos;ll only ping you when these show up.</p>
                </div>
              )}

              {/* Newsletter consent — explicit opt-in required (GDPR Art. 7) */}
              <button
                type="button"
                onClick={() => setPrefs({ ...prefs, newsletterConsent: !prefs.newsletterConsent })}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: '12px',
                  marginTop: '20px', padding: '14px 16px', borderRadius: '12px',
                  border: `1px solid ${prefs.newsletterConsent ? palette.ink : 'rgba(0,0,0,0.1)'}`,
                  background: prefs.newsletterConsent ? palette.cardBg : 'rgba(255,253,247,0.35)',
                  cursor: 'pointer', textAlign: 'left', width: '100%',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
              >
                {/* Checkbox */}
                <div style={{
                  width: 18, height: 18, borderRadius: 5, flexShrink: 0, marginTop: 2,
                  border: `1.5px solid ${prefs.newsletterConsent ? palette.ink : 'rgba(0,0,0,0.3)'}`,
                  background: prefs.newsletterConsent ? palette.ink : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'background 0.15s, border-color 0.15s',
                }}>
                  {prefs.newsletterConsent && (
                    <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3 5-5" stroke={palette.bg} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: '13.5px', fontWeight: 500, color: palette.ink, lineHeight: 1.3, marginBottom: 4 }}>
                    Send me the email newsletter
                  </div>
                  <div style={{ fontSize: '12px', color: palette.muted, lineHeight: 1.5 }}>
                    I agree to receive personalised news digests at the frequency I selected above.
                    You can unsubscribe any time from your preferences. We never share your email.
                  </div>
                </div>
              </button>
            </div>
          )}

          {step === 5 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>What voice suits you?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Extra personalization — not required, but I&apos;ll match your rhythm if you choose.</div>
              <div className="prefs-radio-col">
                {PREF_TONES.map((d) => {
                  const on = prefs.tone === d.id
                  return (
                    <button key={d.id} className={`prefs-radio ${on ? 'on' : ''}`} onClick={() => setOne('tone', d.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : 'rgba(0,0,0,0.1)', background: on ? palette.cardBg : 'rgba(255,253,247,0.4)' }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : 'transparent' }} />
                      <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{d.label}</div>
                    </button>
                  )
                })}
              </div>
              <div className="prefs-slider-row">
                <label className="prefs-slider-label" style={{ color: palette.muted }}>Quiet ↔ Lively</label>
                <input type="range" min="0" max="100" value={prefs.energy ?? 35}
                  onChange={(e) => setPrefs({ ...prefs, energy: +e.target.value })} className="prefs-slider" />
              </div>
            </div>
          )}

        </div>

        <footer className="prefs-foot" style={{ borderColor: 'rgba(0,0,0,0.08)' }}>
          <button className="prefs-back" onClick={() => setStep((s) => Math.max(s - 1, 0))} disabled={step === 0} style={{ color: palette.muted }}>← Back</button>
          <div className="prefs-progress" style={{ color: palette.muted }}>{String(step + 1).padStart(2, '0')} – {String(STEPS.length).padStart(2, '0')}</div>
          {step < STEPS.length - 1 ? (
            <button className="prefs-next" onClick={() => setStep((s) => Math.min(s + 1, STEPS.length - 1))} style={{ background: palette.ink, color: palette.bg }}>Continue →</button>
          ) : (
            <button className="prefs-next" onClick={() => { handleFinish() }} style={{ background: palette.ink, color: palette.bg }}>Save preferences</button>
          )}
        </footer>

        {/* ── Summary overlay ── */}
        {showSummary && (
          <div className="folder-modal-overlay" onClick={() => setShowSummary(false)}>
            <div className="folder-modal" onClick={(e) => e.stopPropagation()} style={{ background: palette.bg, color: palette.ink }}>
              <div className="folder-modal-head">
                <div className="folder-modal-title" style={{ fontFamily: FONTS[displayFont] }}>Resumen</div>
                <button className="folder-modal-close" onClick={() => setShowSummary(false)} style={{ color: palette.muted }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
                </button>
              </div>

              <div className="folder-modal-preview" style={{ borderColor: 'rgba(0,0,0,0.08)', background: palette.cardBg }}>
                <div className="folder-modal-preview-label" style={{ color: palette.muted }}>Nombre del folder</div>
                <div className="folder-modal-preview-name" style={{ color: palette.ink, fontFamily: FONTS[displayFont] }}>
                  {buildFolder().name}
                </div>
                <div className="folder-modal-preview-freq" style={{ color: palette.muted }}>
                  {PREF_DELIVERY.find((d) => d.id === prefs.delivery?.[0])?.label || '—'}
                </div>
              </div>

              <div className="summary-list">
                {[
                  { label: 'Rol', value: PREF_ROLES.find((r) => r.id === prefs.role)?.label },
                  { label: 'Región', value: REGIONS_AUTH.find((r) => r.id === prefs.region)?.label },
                  { label: 'Temas', value: (prefs.topics || []).map((t) => topicMap[t] || t).join(', ') || '—' },
                  { label: 'Profundidad', value: PREF_DEPTHS.find((d) => d.id === prefs.depth)?.label },
                  { label: 'Frecuencia', value: PREF_DELIVERY.find((d) => d.id === prefs.delivery?.[0])?.label },
                  { label: 'Tono', value: PREF_TONES.find((t) => t.id === prefs.tone)?.label },
                ].filter((r) => r.value).map((r) => (
                  <div key={r.label} className="summary-row">
                    <span className="summary-label" style={{ color: palette.muted }}>{r.label}</span>
                    <span className="summary-value" style={{ color: palette.ink }}>{r.value}</span>
                  </div>
                ))}
              </div>

              <div className="folder-form-actions">
                <button className="folder-form-cancel" onClick={() => setShowSummary(false)} style={{ color: palette.muted }}>← Editar</button>
                <button className="folder-form-save" onClick={confirmCreateFolder} style={{ background: palette.ink, color: palette.bg }}>
                  Crear folder
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
