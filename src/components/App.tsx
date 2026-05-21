'use client'

import { useState, useRef, useEffect } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import Sidebar from '@/components/layout/Sidebar'
import Message from '@/components/chat/Message'
import Composer from '@/components/chat/Composer'
import Toast from '@/components/ui/Toast'
import AuthGate from '@/components/auth/AuthGate'
import PrefsDeck from '@/components/preferences/PrefsDeck'
import { TweaksPanel, TweakSection, TweakSelect, TweakSlider, TweakToggle, TweakText } from '@/components/ui/TweaksPanel'
import { PALETTES } from '@/constants/palettes'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { BENCHMARK_CARDS, SUGGESTIONS, TWEAKS_DEFAULTS } from '@/constants/data'
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
          onAuthed={(u) => setUser(u)}
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
        onLogout={() => { writeSession(null); setUser(null) }}
      />

      <main className="main">
        <header className="topbar">
          <div className="crumb" style={{ color: palette.muted }}>
            <span className="crumb-tag" style={{ borderColor: 'rgba(0,0,0,0.1)' }}>AI · Benchmarks</span>
            <span className="crumb-title" style={{ color: palette.ink }}>
              {threads.find((t) => t.id === activeId)?.title || 'Conversation'}
            </span>
          </div>
          <div className="topbar-right" style={{ color: palette.muted }}>
            <button className="ghost-btn" onClick={() => setPrefsOpen(true)}>Preferences</button>
            <button className="ghost-btn">Sources</button>
            <button className="ghost-btn">Save</button>
            <button className="ghost-btn">Share</button>
          </div>
        </header>

        <section className="canvas" ref={scrollRef}>
          {isEmpty ? (
            <div className="hero">
              <div className="hero-eyebrow" style={{ color: palette.muted }}>Good afternoon, {user.name.split(' ')[0]}.</div>
              <h1 className="hero-title" style={{ fontFamily: FONTS[tw.displayFont], color: palette.ink }}>
                Explore AI <span className="hero-news" style={{ fontFamily: NEWS_FONTS[tw.newsFont], color: palette.accent }}>news</span>
              </h1>
              <p className="hero-sub" style={{ color: palette.muted }}>{tw.tagline}</p>
              {tw.showSuggestions && (
                <div className="chips">
                  {SUGGESTIONS.map((s) => (
                    <button key={s.label} className="chip" onClick={() => send(s.prompt)}
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.12)', background: 'rgba(255,253,247,0.55)' }}>
                      {s.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
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
