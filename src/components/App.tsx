'use client'

import { useState, useRef, useEffect } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import Sidebar from '@/components/layout/Sidebar'
import Message from '@/components/chat/Message'
import Composer from '@/components/chat/Composer'
import BriefingPreview from '@/components/chat/BriefingPreview'
import Toast from '@/components/ui/Toast'
import ShareModal from '@/components/ui/ShareModal'
import AuthGate from '@/components/auth/AuthGate'
import PrefsDeck from '@/components/preferences/PrefsDeck'
import { TweaksPanel, TweakSection, TweakSelect, TweakSlider, TweakToggle, TweakText } from '@/components/ui/TweaksPanel'
import { PALETTES } from '@/constants/palettes'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { BENCHMARK_CARDS, SUGGESTIONS, TOPIC_SUGGESTIONS, TWEAKS_DEFAULTS } from '@/constants/data'
import { readSession, writeSession } from '@/lib/session'
import { useTweaks } from '@/hooks/useTweaks'
import type { ChatMessage, NewsCard, Prefs, Thread, User } from '@/types'

declare global {
  interface Window {
    claude?: { complete: (opts: { messages: { role: string; content: string }[] }) => Promise<string> }
  }
}

function buildBenchmarkConvo(): ChatMessage[] {
  return [
    { id: 1, role: 'user', content: 'What are the latest LLM benchmarks?' },
    {
      id: 2, role: 'ai',
      content: `a few things are stirring in benchmark-land this week — none of it dramatic, but the picture is shifting.

the headline is that no single model is sweeping anymore. GPT-5.1 leads on reasoning and code; Claude 4.5 still owns long-context recall and tool-use; Gemini 3 is closer than it's been in months. on the open side, Llama 4.1 just cracked the Arena top five for the first time.

the more interesting story underneath: MMLU-Pro is saturating — five models cluster within two points — and researchers are openly arguing it's time for harder evals. SWE-bench Verified jumped after a new tool-use protocol, which says more about plumbing than raw intelligence.`,
      cards: BENCHMARK_CARDS,
    },
  ]
}

export default function App() {
  const [tw, setTweak] = useTweaks(TWEAKS_DEFAULTS)
  const palette = PALETTES[tw.palette] || PALETTES.moss
  const [user, setUser] = useState<User | null>(null)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin')
  const [prefsOpen, setPrefsOpen] = useState(false)
  const [prefs, setPrefs] = useState<Prefs>({
    role: 'engineer', region: 'eu', topics: ['ai_ml', 'cloud', 'cyber'],
    depth: 'deep', delivery: ['daily'], keywords: '', tone: 'calm', energy: 35,
  })
  const [threads, setThreads] = useState<Thread[]>([
    { id: 't1', title: 'Latest LLM benchmarks',       time: 'Now' },
    { id: 't2', title: 'Frontier releases this week',  time: 'Today' },
    { id: 't3', title: 'Open vs. closed models',       time: 'Yesterday' },
    { id: 't4', title: 'AI policy in the EU',          time: 'Mon' },
    { id: 't5', title: 'What I missed last week',      time: 'Apr 28' },
  ])
  const [activeId, setActiveId] = useState('t1')
  const [messages, setMessages] = useState<ChatMessage[]>(() => tw.preloadDemo ? buildBenchmarkConvo() : [])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [shareOpen, setShareOpen] = useState(false)
  const scrollRef = useRef<HTMLElement>(null)

  useEffect(() => { setUser(readSession()) }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const send = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim()
    if (!text || busy) return
    setInput('')
    const userMsg: ChatMessage = { id: Date.now(), role: 'user', content: text }
    const thinkingId = Date.now() + 1
    setMessages((m) => [...m, userMsg, { id: thinkingId, role: 'ai', thinking: true }])
    setBusy(true)

    if (messages.length === 0) {
      setThreads((ts) => {
        const newTitle = text.length > 40 ? text.slice(0, 40) + '…' : text
        return ts.map((t) => t.id === activeId ? { ...t, title: newTitle, time: 'Just now' } : t)
      })
    }

    try {
      const reply = await window.claude?.complete({
        messages: [{
          role: 'user',
          content: `You are MAI news — a calm, editorial AI-news companion. You ONLY discuss artificial intelligence: models, benchmarks, research papers, releases, policy, infrastructure, the people and companies behind it.

Voice: thoughtful, literary, unhurried. Lowercase is fine. No emoji. No bullet lists unless explicitly asked. Keep replies to 2–4 short paragraphs. Begin without preamble.

User: ${text}`,
        }],
      }) ?? "i'm having trouble reaching my thoughts right now. try again in a moment."
      setMessages((m) => m.map((msg) => msg.id === thinkingId ? { id: thinkingId, role: 'ai', content: reply } : msg))
    } catch {
      setMessages((m) => m.map((msg) => msg.id === thinkingId ? { id: thinkingId, role: 'ai', content: "i'm having trouble reaching my thoughts right now. try again in a moment." } : msg))
    } finally {
      setBusy(false)
    }
  }

  const startNew = () => {
    const id = 't' + Date.now()
    setThreads((ts) => [{ id, title: 'New conversation', time: 'Now' }, ...ts])
    setActiveId(id)
    setMessages([])
  }

  const handleAction = (kind: string, card: NewsCard) => {
    if (kind === 'read') setToast(`Opening ${card.source}…`)
    if (kind === 'more') setToast(`Pulling threads on "${card.tag}"…`)
  }
  const handleActionChip = (a: { id: string; label: string }) => {
    const map: Record<string, string> = {
      report: 'Drafting a one-page report from these stories…',
      compare: 'Building a side-by-side comparison…',
      explore: 'Surfacing related papers and releases…',
      save: 'Saved to your library.',
    }
    setToast(map[a.id] || a.label)
  }

  const tweakControls = (
    <TweaksPanel title="Tweaks">
      <TweakSection title="Mood">
        <TweakSelect label="Palette" value={tw.palette} onChange={(v) => setTweak('palette', v)}
          options={Object.entries(PALETTES).map(([k, v]) => ({ value: k, label: v.name }))} />
        <TweakSelect label="Display font" value={tw.displayFont} onChange={(v) => setTweak('displayFont', v)}
          options={Object.keys(FONTS).map((k) => ({ value: k, label: k }))} />
        <TweakSelect label="'news' font" value={tw.newsFont} onChange={(v) => setTweak('newsFont', v)}
          options={Object.keys(NEWS_FONTS).map((k) => ({ value: k, label: k }))} />
      </TweakSection>
      <TweakSection title="Atmosphere">
        <TweakSlider label="Grain" min={0} max={0.5} step={0.01} value={tw.grain} onChange={(v) => setTweak('grain', v)} />
        <TweakSlider label="Blur" min={20} max={140} step={1} value={tw.blur} onChange={(v) => setTweak('blur', v)} />
      </TweakSection>
      <TweakSection title="Layout">
        <TweakToggle label="Show suggestions" value={tw.showSuggestions} onChange={(v) => setTweak('showSuggestions', v)} />
        <TweakToggle label="Compact messages" value={tw.compactMessages} onChange={(v) => setTweak('compactMessages', v)} />
        <TweakText label="Tagline" value={tw.tagline} onChange={(v) => setTweak('tagline', v)} />
      </TweakSection>
    </TweaksPanel>
  )

  if (!user) {
    return (
      <>
        <AuthGate
          palette={palette} displayFont={tw.displayFont} newsFont={tw.newsFont}
          blur={tw.blur} grain={tw.grain} mode={authMode} setMode={setAuthMode}
          onAuthed={(u) => {
            setUser(u)
            setPrefs((p) => ({
              ...p,
              region: u.region,
              role: u.role || p.role,
              delivery: u.delivery || p.delivery,
            }))
          }}
        />
        {tweakControls}
      </>
    )
  }

  const isEmpty = messages.length === 0

  return (
    <div className="shell" style={{ color: palette.ink, fontFamily: "'Inter Tight', system-ui, sans-serif" }}>
      <Backdrop palette={palette} blur={tw.blur} grain={tw.grain} />

      <Sidebar
        palette={palette} displayFont={tw.displayFont} newsFont={tw.newsFont}
        threads={threads} activeId={activeId}
        onSelect={(id) => { setActiveId(id); setMessages(id === 't1' ? buildBenchmarkConvo() : []) }}
        onNew={startNew} user={user}
        onDelete={(id) => setThreads((ts) => ts.filter((t) => t.id !== id))}
        onPin={(id) => setThreads((ts) => ts.map((t) => t.id === id ? { ...t, pinned: !t.pinned } : t))}
        onLogout={() => { writeSession(null); setUser(null) }}
      />

      <main className="main">
        <header className="topbar">
          <div className="crumb" style={{ color: palette.muted }}>
            <span className="crumb-title" style={{ color: palette.ink }}>
              {threads.find((t) => t.id === activeId)?.title || 'Conversation'}
            </span>
          </div>
          <div className="topbar-right" style={{ color: palette.muted }}>
            <button className="ghost-btn prefs-btn" onClick={() => setPrefsOpen(true)}
              style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.18)', background: 'rgba(255,253,247,0.7)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
              Preferences
            </button>
            <div style={{ position: 'relative' }}>
              <button className="ghost-btn" onClick={() => setShareOpen((v) => !v)}>Share</button>
              <ShareModal open={shareOpen} onClose={() => setShareOpen(false)} palette={palette}
                title={threads.find((t) => t.id === activeId)?.title || 'Conversation'}
                messages={messages} />
            </div>
          </div>
        </header>

        <section className="canvas" ref={scrollRef}>
          {isEmpty ? (
            <BriefingPreview
              palette={palette} displayFont={tw.displayFont} newsFont={tw.newsFont}
              prefs={prefs} user={user} onAsk={(q) => send(q)}
            />
          ) : (
            <div className="thread">
              {messages.map((m) => (
                <Message key={m.id} msg={m} palette={palette} displayFont={tw.displayFont}
                  compact={tw.compactMessages} onAction={handleAction}
                  onActionChip={handleActionChip} onFollowup={(f) => send(f)} />
              ))}
            </div>
          )}
        </section>

        <div className="composer-wrap">
          <Composer value={input} setValue={setInput} onSend={() => send()} palette={palette} disabled={busy} />
        </div>
      </main>

      <Toast text={toast} onDone={() => setToast('')} />

      <PrefsDeck open={prefsOpen} onClose={() => setPrefsOpen(false)} palette={palette}
        displayFont={tw.displayFont} newsFont={tw.newsFont} prefs={prefs} setPrefs={setPrefs}
        user={user} onSave={() => { setPrefsOpen(false); setToast('Preferences saved. I\'ll keep these in mind.') }} />

      {tweakControls}
    </div>
  )
}
