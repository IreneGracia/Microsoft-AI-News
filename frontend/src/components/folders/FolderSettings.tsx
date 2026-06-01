'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import { FONTS } from '@/constants/fonts'
import { PREF_DELIVERY } from '@/constants/preferences'
import type { NewsFolder, Palette } from '@/types'

interface Props {
  folder: NewsFolder
  palette: Palette
  displayFont: string
  onSave: (updated: NewsFolder) => void
  onClose: () => void
}

export default function FolderSettings({ folder, palette, displayFont, onSave, onClose }: Props) {
  const [name, setName] = useState(folder.name)
  const [frequency, setFrequency] = useState(folder.frequency)
  const [keywords, setKeywords] = useState<string[]>(folder.keywords || [])
  const [kwInput, setKwInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const addKeyword = () => {
    const val = kwInput.trim()
    if (val && !keywords.includes(val)) setKeywords((ks) => [...ks, val])
    setKwInput('')
    inputRef.current?.focus()
  }

  const onKwKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addKeyword() }
    if (e.key === 'Backspace' && kwInput === '' && keywords.length > 0)
      setKeywords((ks) => ks.slice(0, -1))
  }

  const handleSave = () => {
    onSave({ ...folder, name: name.trim() || folder.name, frequency, keywords })
  }

  return (
    <div className="folder-modal-overlay" onClick={onClose}>
      <div className="folder-modal folder-settings-modal" onClick={(e) => e.stopPropagation()}
        style={{ background: palette.bg, color: palette.ink }}>

        {/* Header */}
        <div className="folder-modal-head">
          <div className="folder-modal-title" style={{ fontFamily: FONTS[displayFont] }}>
            Folder settings
          </div>
          <button className="folder-modal-close" onClick={onClose} style={{ color: palette.muted }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M6 6l12 12M18 6L6 18"/>
            </svg>
          </button>
        </div>

        {/* Name */}
        <div>
          <label className="folder-form-label" style={{ color: palette.muted }}>Folder name</label>
          <input
            className="folder-form-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ color: palette.ink }}
          />
        </div>

        {/* Frequency */}
        <div>
          <label className="folder-form-label" style={{ color: palette.muted }}>Frequency</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
            {PREF_DELIVERY.map((d) => {
              const on = frequency === d.id
              return (
                <button key={d.id}
                  onClick={() => setFrequency(d.id as NewsFolder['frequency'])}
                  style={{
                    padding: '7px 14px', borderRadius: 999, fontSize: 12.5, fontWeight: 500,
                    border: `1px solid ${on ? palette.ink : 'rgba(0,0,0,0.14)'}`,
                    background: on ? palette.ink : 'rgba(255,253,247,0.55)',
                    color: on ? palette.bg : palette.ink, cursor: 'pointer',
                  }}>
                  {d.label}
                </button>
              )
            })}
          </div>
          <p style={{ fontSize: 11.5, color: palette.muted, marginTop: 6 }}>
            {PREF_DELIVERY.find((d) => d.id === frequency)?.note}
          </p>
        </div>

        {/* Keywords */}
        <div>
          <label className="folder-form-label" style={{ color: palette.muted }}>
            Priority keywords
          </label>
          <p style={{ fontSize: 12, color: palette.muted, margin: '4px 0 8px' }}>
            News matching these keywords will appear first in your briefing.
          </p>
          <div className="kw-input-wrap" style={{ borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.8)' }}>
            {keywords.map((kw) => (
              <span key={kw} className="kw-chip" style={{ background: palette.ink, color: palette.bg }}>
                {kw}
                <button className="kw-chip-del" onClick={() => setKeywords((ks) => ks.filter((k) => k !== kw))}>
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <path d="M18 6L6 18M6 6l12 12"/>
                  </svg>
                </button>
              </span>
            ))}
            <input
              ref={inputRef}
              className="kw-input"
              placeholder={keywords.length === 0 ? 'Add keyword and press Enter…' : ''}
              value={kwInput}
              onChange={(e) => setKwInput(e.target.value)}
              onKeyDown={onKwKeyDown}
              onBlur={addKeyword}
              style={{ color: palette.ink }}
            />
          </div>
          <p style={{ fontSize: 11, color: palette.muted, marginTop: 5 }}>
            Press Enter or comma to add. Backspace to remove the last one.
          </p>
        </div>

        {/* Actions */}
        <div className="folder-form-actions">
          <button className="folder-form-cancel" onClick={onClose} style={{ color: palette.muted }}>
            Cancel
          </button>
          <button className="folder-form-save" onClick={handleSave}
            style={{ background: palette.ink, color: palette.bg }}>
            Save changes
          </button>
        </div>
      </div>
    </div>
  )
}
