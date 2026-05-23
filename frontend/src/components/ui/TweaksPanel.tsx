'use client'

import { useState, useRef, useEffect, useCallback, type ReactNode } from 'react'

// ── TweaksPanel ───────────────────────────────────────────────────────────────

interface PanelProps {
  title?: string
  children: ReactNode
}

export function TweaksPanel({ title = 'Tweaks', children }: PanelProps) {
  const [open, setOpen] = useState(false)
  const dragRef = useRef<HTMLDivElement>(null)
  const offsetRef = useRef({ x: 16, y: 16 })
  const PAD = 16

  const clampToViewport = useCallback(() => {
    const panel = dragRef.current
    if (!panel) return
    const w = panel.offsetWidth, h = panel.offsetHeight
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD)
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD)
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y)),
    }
    panel.style.right = offsetRef.current.x + 'px'
    panel.style.bottom = offsetRef.current.y + 'px'
  }, [])

  useEffect(() => {
    if (!open) return
    clampToViewport()
    const ro = new ResizeObserver(clampToViewport)
    ro.observe(document.documentElement)
    return () => ro.disconnect()
  }, [open, clampToViewport])

  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      const t = e?.data?.type
      if (t === '__activate_edit_mode') setOpen(true)
      else if (t === '__deactivate_edit_mode') setOpen(false)
    }
    window.addEventListener('message', onMsg)
    window.parent.postMessage({ type: '__edit_mode_available' }, '*')
    return () => window.removeEventListener('message', onMsg)
  }, [])

  const dismiss = () => {
    setOpen(false)
    window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*')
  }

  const onDragStart = (e: React.MouseEvent) => {
    const panel = dragRef.current
    if (!panel) return
    const r = panel.getBoundingClientRect()
    const sx = e.clientX, sy = e.clientY
    const startRight = window.innerWidth - r.right
    const startBottom = window.innerHeight - r.bottom
    const move = (ev: MouseEvent) => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy),
      }
      clampToViewport()
    }
    const up = () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }

  if (!open) return null

  return (
    <div
      ref={dragRef}
      className="twk-panel"
      data-noncommentable=""
      style={{ right: offsetRef.current.x, bottom: offsetRef.current.y }}
    >
      <div className="twk-hd" onMouseDown={onDragStart}>
        <b>{title}</b>
        <button
          className="twk-x"
          aria-label="Close tweaks"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={dismiss}
        >
          ✕
        </button>
      </div>
      <div className="twk-body">{children}</div>
    </div>
  )
}

// ── Layout helpers ────────────────────────────────────────────────────────────

export function TweakSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <div className="twk-sect">{title}</div>
      {children}
    </>
  )
}

function TweakRow({ label, value, children, inline = false }: { label: string; value?: string | number; children: ReactNode; inline?: boolean }) {
  return (
    <div className={inline ? 'twk-row twk-row-h' : 'twk-row'}>
      <div className="twk-lbl">
        <span>{label}</span>
        {value != null && <span className="twk-val">{value}</span>}
      </div>
      {children}
    </div>
  )
}

// ── Controls ──────────────────────────────────────────────────────────────────

export function TweakSlider({ label, value, min = 0, max = 100, step = 1, unit = '', onChange }: {
  label: string; value: number; min?: number; max?: number; step?: number; unit?: string; onChange: (v: number) => void
}) {
  return (
    <TweakRow label={label} value={`${value}${unit}`}>
      <input type="range" className="twk-slider" min={min} max={max} step={step}
        value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </TweakRow>
  )
}

export function TweakToggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="twk-row twk-row-h">
      <div className="twk-lbl"><span>{label}</span></div>
      <button type="button" className="twk-toggle" data-on={value ? '1' : '0'}
        role="switch" aria-checked={!!value} onClick={() => onChange(!value)}>
        <i />
      </button>
    </div>
  )
}

export function TweakSelect({ label, value, options, onChange }: {
  label: string; value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <TweakRow label={label}>
      <select className="twk-field" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </TweakRow>
  )
}

export function TweakText({ label, value, placeholder, onChange }: {
  label: string; value: string; placeholder?: string; onChange: (v: string) => void
}) {
  return (
    <TweakRow label={label}>
      <input className="twk-field" type="text" value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)} />
    </TweakRow>
  )
}
