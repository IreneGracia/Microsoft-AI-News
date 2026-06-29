'use client'

import { useState, useRef, useEffect } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import Sidebar from '@/components/layout/Sidebar'
import Message from '@/components/chat/Message'
import Composer from '@/components/chat/Composer'
import BriefingPreview from '@/components/chat/BriefingPreview'
import DashboardView from '@/components/dashboard/DashboardView'
import Toast from '@/components/ui/Toast'
import AuthGate from '@/components/auth/AuthGate'
import PrefsDeck from '@/components/preferences/PrefsDeck'
import SavedView from '@/components/saved/SavedView'
import { TweaksPanel, TweakSection, TweakSelect, TweakSlider, TweakToggle, TweakText } from '@/components/ui/TweaksPanel'
import { PALETTES } from '@/constants/palettes'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { BENCHMARK_CARDS, NEWS_BY_TOPIC, TOPIC_SUGGESTIONS, TWEAKS_DEFAULTS } from '@/constants/data'
import { readSession, writeSession, apiUserToLocal } from '@/lib/session'
import { getToken, setToken, getMe, createSession, deleteSession, streamMessage, listSessions, getPreferences, getSession, getSaved, saveArticle, unsaveArticle, getFolders, createFolder, deleteFolder, createFolderThread, deleteFolderThread, type SseCitation, type ApiArticle, type ApiFolder } from '@/lib/api'
import { useTweaks } from '@/hooks/useTweaks'
import type { ChatMessage, NewsCard, NewsFolder, Prefs, Thread, User } from '@/types'

const FALLBACK_PROMPTS = [
  "What are the biggest AI breakthroughs this week?",
  "Which tech companies made headlines today?",
  "Catch me up on the latest in cloud infrastructure.",
  "What should I know about AI regulation right now?",
]

function NewChatScreen({ palette, displayFont, prefs, user, onAsk }: {
  palette: import('@/types').Palette
  displayFont: string
  prefs: Prefs
  user: User
  onAsk: (q: string) => void
}) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const firstName = user.name?.split(' ')[0] || 'there'

  const topicQuestions = (prefs.topics ?? [])
    .slice(0, 3)
    .map((t) => TOPIC_SUGGESTIONS[t]?.prompt)
    .filter(Boolean) as string[]

  const prompts = [
    ...topicQuestions,
    ...FALLBACK_PROMPTS,
  ]
    .filter((v, i, a) => a.indexOf(v) === i)
    .slice(0, 4)

  return (
    <div className="newchat-wrap">
      <h2 className="newchat-greeting" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
        {greeting}, {firstName}.
      </h2>
      <p className="newchat-sub" style={{ color: palette.muted }}>Here's what's making news today. Ask me anything.</p>
      <ul className="newchat-prompts">
        {prompts.map((q) => (
          <li key={q}>
            <button className="newchat-prompt" onClick={() => onAsk(q)}
              style={{ color: palette.ink, background: 'rgba(255,253,247,0.38)', borderColor: 'rgba(0,0,0,0.07)', fontFamily: FONTS[displayFont] }}>
              <span className="newchat-prompt-text">{q}</span>
              <span className="newchat-prompt-arrow" style={{ color: palette.muted }}>→</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function _apiArticleToCard(a: ApiArticle): NewsCard {
  return {
    id: a.id,
    title: a.title,
    source: a.source,
    time: a.published_at
      ? new Date(a.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      : '',
    kind: 'article',
    blurb: a.extract ?? '',
    tone: 'calm',
    tag: a.source,
    image_url: a.image_url,
  }
}

function _apiFolderToLocal(f: ApiFolder): NewsFolder {
  return {
    id: f.id,
    name: f.name,
    topics: f.topics,
    frequency: (f.frequency as NewsFolder['frequency']) || 'daily',
    keywords: f.keywords,
    threads: f.threads.map((t) => ({ id: t.id, title: t.title ?? 'Untitled', time: t.time })),
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
    role: 'for_engineers_technical_depth', region: 'europe', topics: [],
    depth: 'deep', delivery: ['daily'], keywords: '', tone: 'technical', energy: 35,
  })
  const [folders, setFolders] = useState<NewsFolder[]>([])

  const [currentView, setCurrentView] = useState<'dashboard' | 'chat' | 'saved'>('dashboard')
  const [savedArticleIds, setSavedArticleIds] = useState<Set<string>>(new Set())
  const [savedArticles, setSavedArticles] = useState<NewsCard[]>([])

  const toggleSave = async (card: NewsCard) => {
    const isSaved = savedArticleIds.has(card.id)
    // Optimistic update
    setSavedArticleIds((ids) => {
      const next = new Set(ids)
      isSaved ? next.delete(card.id) : next.add(card.id)
      return next
    })
    setSavedArticles((as) =>
      isSaved ? as.filter((a) => a.id !== card.id) : [card, ...as.filter((a) => a.id !== card.id)]
    )
    setToast(isSaved ? 'Removed from saved.' : 'Article saved.')

    if (getToken()) {
      try {
        if (isSaved) {
          await unsaveArticle(card.id)
        } else {
          await saveArticle(card.id)
        }
      } catch {
        // Roll back optimistic update on failure
        setSavedArticleIds((ids) => {
          const next = new Set(ids)
          isSaved ? next.add(card.id) : next.delete(card.id)
          return next
        })
        setSavedArticles((as) =>
          isSaved ? [card, ...as.filter((a) => a.id !== card.id)] : as.filter((a) => a.id !== card.id)
        )
        setToast('Could not save — try again.')
      }
    }
  }

  const [activeFolderId, setActiveFolderId] = useState<string | null>(null)
  const [activeThreadId, setActiveThreadId] = useState('')
  const [generalThreads, setGeneralThreads] = useState<Thread[]>([])
  const sessionMap = useRef<Map<string, string>>(new Map())
  // When true, next send() will always start a fresh general session regardless of current state
  const freshChatRef = useRef(false)

  const addGeneralThread = () => {
    // Don't create a session or add to Recents yet — wait for the first message
    setActiveFolderId(null)
    setActiveThreadId('')
    setMessages([])
  }

  const deleteGeneralThread = async (threadId: string) => {
    setGeneralThreads((ts) => ts.filter((t) => t.id !== threadId))
    const sessionId = sessionMap.current.get(threadId)
    if (sessionId) {
      sessionMap.current.delete(threadId)
      await deleteSession(sessionId).catch(() => {/* best-effort */})
    }
  }

  const buildFolderBriefing = (folder: NewsFolder): ChatMessage[] => {
    const now = new Date()
    const freqPrefix = { daily: 'DAILY BRIEF', weekly: 'WEEKLY DIGEST', breaking: 'BREAKING NEWS' }[folder.frequency] ?? 'DAILY BRIEF'
    const dayName = now.toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase()
    const dateStr = now.toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' }).toUpperCase()
    const header = `${freqPrefix} · ${dayName}, ${dateStr}`

    const hour = now.getHours()
    const timeGreeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
    const firstName = user?.name?.split(' ')[0] || 'there'
    const greeting = `${timeGreeting}, ${firstName}.`

    const kw = (folder.keywords || []).map((k) => k.toLowerCase())
    const allCards = folder.topics.flatMap((t) => NEWS_BY_TOPIC[t] ?? [])
    const cards = (kw.length > 0
      ? [...allCards].sort((a, b) => {
          const aHit = kw.some((k) => a.title.toLowerCase().includes(k) || a.blurb.toLowerCase().includes(k))
          const bHit = kw.some((k) => b.title.toLowerCase().includes(k) || b.blurb.toLowerCase().includes(k))
          return (bHit ? 1 : 0) - (aHit ? 1 : 0)
        })
      : allCards
    ).slice(0, 3)
    const followups = folder.topics
      .map((t) => TOPIC_SUGGESTIONS[t]?.prompt)
      .filter(Boolean)
      .slice(0, 4) as string[]

    return [{
      id: Date.now(),
      role: 'ai',
      cards: cards.length > 0 ? cards : undefined,
      briefing: {
        header,
        greeting,
        subtitle: `Here's what's moving in your topics today. Click any story to go deeper.`,
        followups,
      },
    }]
  }

  const addThread = async (folderId: string) => {
    const folder = folders.find((f) => f.id === folderId)
    const briefing = folder ? buildFolderBriefing(folder) : []
    const firstTitle = folder?.topics[0]
      ? (briefing[0]?.cards?.[0]?.title?.slice(0, 40) ?? 'New conversation')
      : 'New conversation'
    setMessages(briefing)
    if (getToken()) {
      try {
        const thread = await createFolderThread(folderId, firstTitle)
        sessionMap.current.set(thread.id, thread.id)
        setFolders((fs) => fs.map((f) => f.id === folderId
          ? { ...f, threads: [{ id: thread.id, title: thread.title ?? firstTitle, time: thread.time }, ...f.threads] }
          : f
        ))
        setActiveFolderId(folderId)
        setActiveThreadId(thread.id)
      } catch {
        const id = 'th' + Date.now()
        setFolders((fs) => fs.map((f) => f.id === folderId
          ? { ...f, threads: [{ id, title: firstTitle, time: 'Now' }, ...f.threads] }
          : f
        ))
        setActiveFolderId(folderId)
        setActiveThreadId(id)
      }
    } else {
      const id = 'th' + Date.now()
      setFolders((fs) => fs.map((f) => f.id === folderId
        ? { ...f, threads: [{ id, title: firstTitle, time: 'Now' }, ...f.threads] }
        : f
      ))
      setActiveFolderId(folderId)
      setActiveThreadId(id)
    }
  }

  const deleteThread = async (folderId: string, threadId: string) => {
    setFolders((fs) => fs.map((f) => f.id === folderId
      ? { ...f, threads: f.threads.filter((t) => t.id !== threadId) }
      : f
    ))
    sessionMap.current.delete(threadId)
    if (getToken()) {
      await deleteFolderThread(folderId, threadId).catch(() => {})
    }
  }

  const [messages, setMessages] = useState<ChatMessage[]>(() => tw.preloadDemo ? buildBenchmarkConvo() : [])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const scrollRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const onExpired = () => { writeSession(null); setUser(null) }
    window.addEventListener('mai:session-expired', onExpired)
    return () => window.removeEventListener('mai:session-expired', onExpired)
  }, [])

  useEffect(() => {
    // Magic-link verify redirects back as: {frontend_url}/#access_token=<jwt>
    const hash = window.location.hash
    if (hash.includes('access_token=')) {
      const token = new URLSearchParams(hash.slice(1)).get('access_token')
      if (token) {
        setToken(token)
        window.history.replaceState(null, '', window.location.pathname)
        getMe()
          .then((apiUser) => {
            const u = apiUserToLocal(apiUser)
            writeSession(u)
            setUser(u)
          })
          .catch(() => {
            setToken(null)
            setUser(readSession())
          })
        return
      }
    }
    setUser(readSession())
  }, [])

  useEffect(() => {
    if (!user || !getToken()) return

    getPreferences().then((p) => {
      setPrefs((curr) => ({
        ...curr,
        topics: p.topics.length > 0 ? p.topics : curr.topics,
        region: p.regions[0] ?? curr.region,
        role: p.role ?? curr.role,
        depth: p.length ?? curr.depth,
        delivery: [p.frequency],
        tone: p.tone ?? curr.tone,
      }))
    }).catch(() => {})

    Promise.all([listSessions(), getFolders()]).then(([sessions, apiFolders]) => {
      const local = apiFolders.map(_apiFolderToLocal)
      setFolders(local)
      local.forEach((f) => f.threads.forEach((t) => sessionMap.current.set(t.id, t.id)))

      const folderSessionIds = new Set(local.flatMap((f) => f.threads.map((t) => t.id)))
      const generalOnly = sessions.filter((s) => !folderSessionIds.has(s.id))
      setGeneralThreads(generalOnly.map((s) => ({
        id: s.id,
        title: s.title ?? 'Untitled chat',
        time: new Date(s.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      })))
      generalOnly.forEach((s) => sessionMap.current.set(s.id, s.id))
    }).catch(() => {})

    getSaved().then((articles) => {
      const cards = articles.map(_apiArticleToCard)
      setSavedArticles(cards)
      setSavedArticleIds(new Set(cards.map((c) => c.id)))
    }).catch(() => {})
  }, [user])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSelectThread = async (folderId: string | null, threadId: string) => {
    setActiveFolderId(folderId)
    setActiveThreadId(threadId)
    setMessages([])
    const sessionId = sessionMap.current.get(threadId)
    if (sessionId && getToken()) {
      try {
        const sess = await getSession(sessionId)
        if (sess.messages.length > 0) {
          setMessages(sess.messages.map((m, i) => ({
            id: i + 1,
            role: m.role === 'assistant' ? 'ai' as const : 'user' as const,
            content: m.content,
            cards: m.citations.length > 0
              ? m.citations.slice(0, 3).map((c, j) => ({
                  id: c.article_id,
                  source: c.source,
                  time: c.published_at
                    ? new Date(c.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                    : '',
                  kind: 'article',
                  title: c.title,
                  blurb: '',
                  tone: j === 0 ? 'lead' as const : 'calm' as const,
                  tag: c.source,
                  image_url: (c as { image_url?: string | null }).image_url,
                }))
              : undefined,
          })))
        }
      } catch { /* stay empty on failure */ }
    }
  }

  const send = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim()
    if (!text || busy) return
    setCurrentView('chat')
    setInput('')
    const userMsg: ChatMessage = { id: Date.now(), role: 'user', content: text }
    const thinkingId = Date.now() + 1
    setMessages((m) => [...m, userMsg, { id: thinkingId, role: 'ai', thinking: true }])
    setBusy(true)

    const token = getToken()
    if (!token) {
      setMessages((m) => m.map((msg) => msg.id === thinkingId
        ? { id: thinkingId, role: 'ai', content: "i'm not connected to the server right now. try signing in again." }
        : msg))
      setBusy(false)
      return
    }

    const isFresh = freshChatRef.current
    freshChatRef.current = false
    const effectiveFolderId = isFresh ? null : activeFolderId
    let sessionId = isFresh ? undefined : sessionMap.current.get(activeThreadId)
    if (!sessionId) {
      try {
        const session = await createSession(text.slice(0, 80))
        sessionId = session.id
        sessionMap.current.set(session.id, session.id)
        // First message in a general chat: register in Recents now
        if (effectiveFolderId === null) {
          setGeneralThreads((ts) => [
            { id: session.id, title: text.slice(0, 60), time: 'Now' },
            ...ts,
          ])
          setActiveFolderId(null)
          setActiveThreadId(session.id)
        }
      } catch {
        setMessages((m) => m.map((msg) => msg.id === thinkingId
          ? { id: thinkingId, role: 'ai', content: "couldn't create a session. please try again." }
          : msg))
        setBusy(false)
        return
      }
    }

    let streamedText = ''
    const citations: SseCitation[] = []

    await streamMessage(sessionId, text, {
      onToken: (chunk) => {
        streamedText += chunk
        setMessages((m) => m.map((msg) => msg.id === thinkingId
          ? { id: thinkingId, role: 'ai', content: streamedText, thinking: false }
          : msg))
      },
      onCitation: (c) => { citations.push(c) },
      onDone: () => {
        const sliced = citations.slice(0, 3)
        const cards: NewsCard[] | undefined = sliced.length > 0
          ? sliced.map((c, i) => ({
              id: c.article_id,
              source: c.source,
              time: new Date(c.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
              kind: 'article',
              title: c.title,
              blurb: '',
              tone: (i === 0 && sliced.length !== 2) ? 'lead' as const : 'calm' as const,
              tag: c.source,
              image_url: c.image_url,
            }))
          : undefined
        setMessages((m) => m.map((msg) => msg.id === thinkingId
          ? { id: thinkingId, role: 'ai', content: streamedText, thinking: false, cards }
          : msg))
        setBusy(false)
      },
      onError: () => {
        setMessages((m) => m.map((msg) => msg.id === thinkingId
          ? { id: thinkingId, role: 'ai', content: streamedText || "i'm having trouble reaching my thoughts right now. try again in a moment." }
          : msg))
        setBusy(false)
      },
    })
  }

  const handleAction = (kind: string, card: NewsCard) => {
    if (kind === 'read') setToast(`Opening ${card.source}…`)
    if (kind === 'more') setToast(`Pulling threads on "${card.tag}"…`)
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
        folders={folders} activeFolderId={activeFolderId} activeThreadId={activeThreadId}
        generalThreads={generalThreads}
        currentView={currentView} onSetView={(v) => {
          setCurrentView(v)
          if (v === 'chat') { setActiveFolderId(null); setActiveThreadId(''); setMessages([]) }
        }}
        onSelectThread={(fId, tId) => { setCurrentView('chat'); handleSelectThread(fId, tId) }}
        onNewThread={addThread}
        onDeleteThread={deleteThread}
        onNewChat={() => { setCurrentView('chat'); addGeneralThread() }}
        onDeleteGeneralThread={deleteGeneralThread}
        onAddFolder={async (name) => {
            if (getToken()) {
              try {
                const apiFolder = await createFolder({ name })
                setFolders((fs) => [...fs, _apiFolderToLocal(apiFolder)])
                setToast(`Folder "${apiFolder.name}" created.`)
              } catch {
                setToast('Could not create folder — try again.')
              }
            } else {
              const local: NewsFolder = { id: 'f' + Date.now(), name, topics: [], frequency: 'daily', keywords: [], threads: [] }
              setFolders((fs) => [...fs, local])
              setToast(`Folder "${name}" created.`)
            }
          }}
        onDeleteFolder={async (id) => {
            setFolders((fs) => fs.filter((f) => f.id !== id))
            if (getToken()) deleteFolder(id).catch(() => {})
          }}
        user={user}
        onLogout={() => { writeSession(null); setToken(null); sessionMap.current.clear(); setUser(null) }}
      />

      <main className="main">
        <header className="topbar">
          <div className="crumb" style={{ color: palette.muted }}>
            {currentView === 'dashboard' ? (
              <span className="crumb-title" style={{ color: palette.ink }}>Dashboard</span>
            ) : currentView === 'saved' ? (
              <span className="crumb-title" style={{ color: palette.ink }}>Saved</span>
            ) : activeFolderId !== null ? (
              <span className="crumb-title" style={{ color: palette.ink }}>
                {folders.find((f) => f.id === activeFolderId)?.name || 'Folder'}
              </span>
            ) : activeThreadId && generalThreads.find((t) => t.id === activeThreadId) ? (
              <span className="crumb-title" style={{ color: palette.ink }}>
                {generalThreads.find((t) => t.id === activeThreadId)?.title}
              </span>
            ) : (
              <button className="crumb-title crumb-new-btn" style={{ color: palette.ink }}
                onClick={() => { setCurrentView('chat'); addGeneralThread() }}>
                New chat
              </button>
            )}
          </div>
          <div className="topbar-right" style={{ color: palette.muted }}>
            <button className="ghost-btn prefs-btn icon-btn" onClick={() => setPrefsOpen(true)}
              style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.18)', background: 'rgba(255,253,247,0.7)' }}
              aria-label="Preferences">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </button>
          </div>
        </header>

        <section className={`canvas${currentView === 'dashboard' ? ' canvas--dashboard' : ''}`} ref={scrollRef}>
          {currentView === 'dashboard' ? (
            <DashboardView palette={palette} displayFont={tw.displayFont}
              userTopics={prefs.topics}
              onAsk={(q) => { freshChatRef.current = true; setMessages([]); send(q) }} />
          ) : currentView === 'saved' ? (
            <SavedView palette={palette} displayFont={tw.displayFont}
              savedArticles={savedArticles} savedIds={savedArticleIds}
              onToggleSave={toggleSave} onAction={handleAction} />
          ) : isEmpty && activeThreadId === '' ? (
            <NewChatScreen palette={palette} displayFont={tw.displayFont}
              prefs={prefs} user={user} onAsk={(q) => send(q)} />
          ) : isEmpty && activeFolderId !== null ? (
            <BriefingPreview palette={palette} displayFont={tw.displayFont}
              prefs={prefs} user={user} onAsk={(q) => send(q)} />
          ) : isEmpty ? null : (
            <div className="thread">
              {messages.map((m) => (
                <Message key={m.id} msg={m} palette={palette} displayFont={tw.displayFont}
                  compact={tw.compactMessages} onAction={handleAction} />
              ))}
            </div>
          )}
        </section>

        {currentView === 'chat' && (
          <div className="composer-wrap">
            <Composer value={input} setValue={setInput} onSend={() => send()} palette={palette} disabled={busy} />
          </div>
        )}
      </main>

      <Toast text={toast} onDone={() => setToast('')} />

      <PrefsDeck
        open={prefsOpen}
        onClose={() => setPrefsOpen(false)}
        palette={palette} displayFont={tw.displayFont} newsFont={tw.newsFont}
        prefs={prefs} setPrefs={setPrefs}
        user={user}
        onCreateFolder={async (localFolder) => {
            setPrefsOpen(false)
            if (getToken()) {
              try {
                const apiFolder = await createFolder({
                  name: localFolder.name,
                  topics: localFolder.topics,
                  frequency: localFolder.frequency,
                  keywords: localFolder.keywords,
                })
                setFolders((fs) => [...fs, _apiFolderToLocal(apiFolder)])
                setToast(`Folder "${apiFolder.name}" created.`)
              } catch {
                setToast('Could not create folder — try again.')
              }
            } else {
              setFolders((fs) => [...fs, localFolder])
              setToast(`Folder "${localFolder.name}" created.`)
            }
          }}
        onSave={() => {
          setPrefsOpen(false)
          setToast('Preferences saved.')
          // Re-fetch from API so `prefs.topics` reflects what was actually stored,
          // which triggers DashboardView to re-fetch with the new topic filter.
          if (getToken()) {
            getPreferences().then((p) => {
              setPrefs((curr) => ({
                ...curr,
                topics: p.topics,
                region: p.regions[0] ?? curr.region,
                role: p.role ?? curr.role,
                depth: p.length ?? curr.depth,
                delivery: [p.frequency],
                tone: p.tone ?? curr.tone,
              }))
            }).catch(() => {})
          }
        }}
      />

      {tweakControls}
    </div>
  )
}
