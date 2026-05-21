const { useState, useEffect, useRef, useMemo } = React;

const TWEAKS_DEFAULTS = /*EDITMODE-BEGIN*/{
  "palette": "moss",
  "displayFont": "Instrument Serif",
  "grain": 0.18,
  "blur": 60,
  "showSuggestions": true,
  "compactMessages": false,
  "tagline": "Today in AI, gently unpacked.",
  "newsFont": "Bricolage Grotesque",
  "preloadDemo": true
} /*EDITMODE-END*/;

// ---------- palettes ----------
const PALETTES = {
  moss: {
    name: "Moss & Ember",
    bg: "#f4ede1", ink: "#1f1d18", muted: "#6b6557",
    blobs: ["#5a6b3d", "#c66a3a", "#d9a05b", "#3a4a3c"],
    accent: "#5a6b3d",
    bubbleAi: "rgba(255,253,247,0.72)",
    bubbleUser: "#1f1d18", bubbleUserInk: "#f4ede1",
    cardBg: "rgba(255,253,247,0.78)"
  },
  rose: {
    name: "Rose Dust",
    bg: "#f1e3da", ink: "#2a1f1c", muted: "#7a6660",
    blobs: ["#c98c8c", "#d9a89a", "#a86e6e", "#e9b48a"],
    accent: "#a86e6e",
    bubbleAi: "rgba(255,250,245,0.74)",
    bubbleUser: "#2a1f1c", bubbleUserInk: "#f1e3da",
    cardBg: "rgba(255,250,245,0.82)"
  },
  ochre: {
    name: "Ochre Field",
    bg: "#f3e7c6", ink: "#211c11", muted: "#6e6347",
    blobs: ["#caa14a", "#8a6b2e", "#d97a3a", "#5a5a2c"],
    accent: "#8a6b2e",
    bubbleAi: "rgba(255,251,238,0.76)",
    bubbleUser: "#211c11", bubbleUserInk: "#f3e7c6",
    cardBg: "rgba(255,251,238,0.84)"
  },
  teal: {
    name: "Teal Dusk",
    bg: "#e6e7e1", ink: "#15201f", muted: "#5a6562",
    blobs: ["#3d6b66", "#2a4a4a", "#a89a6a", "#c4836a"],
    accent: "#3d6b66",
    bubbleAi: "rgba(252,253,250,0.74)",
    bubbleUser: "#15201f", bubbleUserInk: "#e6e7e1",
    cardBg: "rgba(252,253,250,0.82)"
  }
};

const FONTS = {
  "Instrument Serif": "'Instrument Serif', 'Cormorant Garamond', Georgia, serif",
  "Fraunces": "'Fraunces', 'Cormorant Garamond', Georgia, serif",
  "DM Serif Display": "'DM Serif Display', 'Cormorant Garamond', Georgia, serif"
};
const NEWS_FONTS = {
  "Bricolage Grotesque": "'Bricolage Grotesque', sans-serif",
  "Space Grotesk": "'Space Grotesk', sans-serif",
  "Major Mono": "'Major Mono Display', monospace"
};

// ---------- Auth: corporate domain + taxonomy ----------
const CORPORATE_DOMAIN = "microsoft.com";

const DEPARTMENTS = [
  "Engineering",
  "Cloud + AI",
  "Azure",
  "Research",
  "Product",
  "Security",
  "Marketing",
  "Sales",
  "Customer Success",
  "Consulting Services",
  "Legal & Compliance",
  "Finance",
  "Operations",
  "HR / People",
  "Other"
];

const REGIONS_AUTH = [
  { id: "na",    label: "North America" },
  { id: "eu",    label: "Europe" },
  { id: "china", label: "Greater China" },
  { id: "apac",  label: "Asia Pacific" },
  { id: "india", label: "India" },
  { id: "latam", label: "Latin America" },
  { id: "mea",   label: "Middle East & Africa" }
];

function readSession() {
  try { const raw = localStorage.getItem('mai_user'); return raw ? JSON.parse(raw) : null; }
  catch (e) { return null; }
}
function writeSession(u) {
  try {
    if (u) localStorage.setItem('mai_user', JSON.stringify(u));
    else localStorage.removeItem('mai_user');
  } catch (e) {}
}

// ---------- Grain ----------
const grainSvg = (opacity) => `data:image/svg+xml;utf8,${encodeURIComponent(`
<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>
  <filter id='n'>
    <feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>
    <feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 ${opacity} 0'/>
  </filter>
  <rect width='100%' height='100%' filter='url(#n)'/>
</svg>`)}`;

function Backdrop({ palette, blur, grain }) {
  return (
    <div className="backdrop" aria-hidden="true">
      <div className="bd-base" style={{ background: palette.bg }} />
      <div className="bd-blobs" style={{ filter: `blur(${blur}px) saturate(0.95)` }}>
        <span className="blob b1" style={{ background: palette.blobs[0] }} />
        <span className="blob b2" style={{ background: palette.blobs[1] }} />
        <span className="blob b3" style={{ background: palette.blobs[2] }} />
        <span className="blob b4" style={{ background: palette.blobs[3] }} />
      </div>
      <div className="bd-grain" style={{ backgroundImage: `url("${grainSvg(grain)}")` }} />
      <div className="bd-vignette" />
    </div>);

}

function MaiMark({ palette, size = 36 }) {
  return (
    <div className="mai-mark" style={{ width: size, height: size }}>
      <div className="mm-grain" style={{ background: `radial-gradient(circle at 30% 30%, ${palette.blobs[1]}, ${palette.blobs[0]} 55%, ${palette.blobs[3]} 100%)` }} />
      <div className="mm-grain-overlay" style={{ backgroundImage: `url("${grainSvg(0.35)}")` }} />
    </div>);

}

// ---------- Brand wordmark: MAI news ----------
function Wordmark({ palette, displayFont, newsFont, size = 26 }) {
  return (
    <span className="wordmark" style={{ color: palette.ink }}>
      <span className="wm-mai" style={{ fontFamily: FONTS[displayFont], fontSize: size }}>MAI</span>
      <span className="wm-news" style={{ fontFamily: NEWS_FONTS[newsFont], fontSize: size * 0.5, color: palette.accent }}>news</span>
    </span>);

}

// ---------- Suggestion chips (AI-news only) ----------
const SUGGESTIONS = [
{ label: "Latest LLM benchmarks", prompt: "What are the latest LLM benchmarks?" },
{ label: "Frontier model releases this week", prompt: "Walk me through frontier model releases this week." },
{ label: "AI policy in the EU", prompt: "Catch me up on AI policy in the EU." },
{ label: "Open vs. closed models", prompt: "Where does the open-vs-closed model debate stand right now?" }];


// ---------- Pre-seeded LLM benchmark cards ----------
const BENCHMARK_CARDS = [
{
  id: "c1",
  source: "Artificial Analysis",
  time: "2h ago",
  kind: "Benchmark",
  title: "GPT-5.1 edges Claude 4.5 on reasoning, trails on long-context recall",
  blurb: "On the latest combined index, GPT-5.1 takes the lead on math and code, while Claude 4.5 holds long-context retrieval and tool-use. Gemini 3 closes the gap.",
  tone: "lead",
  tag: "Reasoning"
},
{
  id: "c2",
  source: "LMSys Arena",
  time: "5h ago",
  kind: "Leaderboard",
  title: "Open-weights climb: Llama 4.1 enters Arena top five for the first time",
  blurb: "Crowd-rated head-to-head puts Meta's Llama 4.1 within 18 Elo of the leading closed model. DeepSeek-R2 and Qwen 3 follow closely behind.",
  tone: "calm",
  tag: "Open weights"
},
{
  id: "c3",
  source: "MMLU-Pro",
  time: "Yesterday",
  kind: "Analysis",
  title: "Saturation watch: top scores cluster within two points",
  blurb: "Five frontier models now score within a narrow band on MMLU-Pro. Researchers argue the benchmark is approaching its ceiling and call for harder evals.",
  tone: "calm",
  tag: "Saturation"
},
{
  id: "c4",
  source: "SWE-bench Verified",
  time: "Yesterday",
  kind: "Coding",
  title: "Agentic coding scores jump 11 points after new tool-use protocol",
  blurb: "After adopting a standardized tool-use schema, three frontier models posted double-digit gains on real-world software engineering tasks.",
  tone: "calm",
  tag: "Agents"
}];


// ---------- Action chips inside AI cards section ----------
const CARD_ACTIONS = [
{ id: "report", label: "Make a report", icon: "doc" },
{ id: "compare", label: "Compare models", icon: "compare" },
{ id: "explore", label: "Explore deeper", icon: "compass" },
{ id: "save", label: "Save thread", icon: "bookmark" }];


const FOLLOWUPS = [
"Which benchmarks should I actually trust?",
"How is GPT-5.1 different from Claude 4.5 in practice?",
"Show me the open-weights leaderboard.",
"Draft me a one-page summary I can share."];


function Icon({ name, size = 14 }) {
  const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" };
  const map = {
    doc: <g {...stroke}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 13h6M9 17h6M9 9h2" /></g>,
    compare: <g {...stroke}><path d="M3 7h7M3 7l3-3M3 7l3 3" /><path d="M21 17h-7M21 17l-3-3M21 17l-3 3" /></g>,
    compass: <g {...stroke}><circle cx="12" cy="12" r="9" /><path d="m15 9-4 2-2 4 4-2 2-4z" /></g>,
    bookmark: <g {...stroke}><path d="M6 4h12v17l-6-4-6 4z" /></g>,
    arrow: <g {...stroke}><path d="M5 12h14M13 6l6 6-6 6" /></g>,
    external: <g {...stroke}><path d="M14 5h5v5" /><path d="M19 5l-9 9" /><path d="M19 14v5H5V5h5" /></g>,
    sparkle: <g {...stroke}><path d="M12 4v6M12 14v6M4 12h6M14 12h6" /></g>
  };
  return <svg width={size} height={size} viewBox="0 0 24 24">{map[name] || null}</svg>;
}

// ---------- News card ----------
function NewsCard({ card, palette, onAction }) {
  const isLead = card.tone === "lead";
  return (
    <article
      className={`ncard ${isLead ? "ncard-lead" : ""}`}
      style={{
        background: palette.cardBg,
        borderColor: "rgba(0,0,0,0.07)",
        color: palette.ink
      }}>
      
      <div className="ncard-meta" style={{ color: palette.muted }}>
        <span className="ncard-source">{card.source}</span>
        <span className="ncard-dot">·</span>
        <span>{card.time}</span>
        <span className="ncard-tag" style={{ background: palette.ink, color: palette.bg }}>{card.tag}</span>
      </div>
      <h3 className="ncard-title" style={{ color: palette.ink }}>{card.title}</h3>
      <p className="ncard-blurb" style={{ color: palette.muted }}>{card.blurb}</p>
      <div className="ncard-actions">
        <button className="ncard-link" onClick={() => onAction("read", card)} style={{ color: palette.ink }}>
          Read article <Icon name="external" size={12} />
        </button>
        <button className="ncard-link soft" onClick={() => onAction("more", card)} style={{ color: palette.muted }}>
          Explore more
        </button>
      </div>
    </article>);

}

function CardsBlock({ cards, palette, onAction, onActionChip, onFollowup }) {
  return (
    <div className="cards-block">
      <div className="cards-grid">
        {cards.map((c) => <NewsCard key={c.id} card={c} palette={palette} onAction={onAction} />)}
      </div>
      <div className="action-row">
        {CARD_ACTIONS.map((a) =>
        <button
          key={a.id}
          className="action-chip"
          onClick={() => onActionChip(a)}
          style={{ color: palette.ink, borderColor: "rgba(0,0,0,0.12)", background: "rgba(255,253,247,0.6)" }}>
          
            <Icon name={a.icon} />
            <span>{a.label}</span>
          </button>
        )}
      </div>
      <div className="followups">
        <div className="followups-label" style={{ color: palette.muted }}>Or ask</div>
        {FOLLOWUPS.map((f) =>
        <button
          key={f}
          className="followup"
          onClick={() => onFollowup(f)}
          style={{ color: palette.ink, borderColor: "rgba(0,0,0,0.08)" }}>
          
            <span>{f}</span>
            <Icon name="arrow" size={13} />
          </button>
        )}
      </div>
    </div>);

}

// ---------- Message ----------
function Message({ msg, palette, displayFont, compact, onAction, onActionChip, onFollowup }) {
  const isUser = msg.role === "user";
  return (
    <div className={`msg ${isUser ? "msg-user" : "msg-ai"} ${compact ? "msg-compact" : ""}`}>
      {!isUser &&
      <div className="msg-byline" style={{ fontFamily: FONTS[displayFont], color: palette.muted }}>
          MAI
        </div>
      }
      {msg.thinking ?
      <div className="bubble bubble-ai" style={{ background: palette.bubbleAi, color: palette.ink, borderColor: "rgba(0,0,0,0.06)" }}>
          <span className="thinking"><span className="dot" /><span className="dot" /><span className="dot" /></span>
        </div> :

      <>
          {msg.content &&
        <div
          className={`bubble ${isUser ? "bubble-user" : "bubble-ai"}`}
          style={isUser ?
          { background: palette.bubbleUser, color: palette.bubbleUserInk } :
          { background: palette.bubbleAi, color: palette.ink, borderColor: "rgba(0,0,0,0.06)" }}>
          
              <span className="bubble-text">{msg.content}</span>
            </div>
        }
          {msg.cards &&
        <CardsBlock
          cards={msg.cards}
          palette={palette}
          onAction={onAction}
          onActionChip={onActionChip}
          onFollowup={onFollowup} />

        }
        </>
      }
    </div>);

}

// ---------- Composer ----------
function Composer({ value, setValue, onSend, palette, disabled }) {
  const taRef = useRef(null);
  useEffect(() => {
    const el = taRef.current;if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 220) + "px";
  }, [value]);

  return (
    <form className="composer" onSubmit={(e) => {e.preventDefault();onSend();}}>
      <div className="composer-inner" style={{ background: "rgba(255,253,247,0.86)" }}>
        <MaiMark palette={palette} size={28} />
        <textarea
          ref={taRef}
          className="composer-input"
          placeholder="Ask about a model, a benchmark, a paper…"
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {e.preventDefault();onSend();}
          }}
          style={{ color: palette.ink }} />
        
        <div className="composer-actions">
          <button type="button" className="icon-btn" title="Voice" aria-label="Voice" style={{ color: palette.muted }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" />
            </svg>
          </button>
          <button type="submit" className="send-btn" disabled={disabled || !value.trim()} style={{ background: palette.ink, color: palette.bg }} aria-label="Send">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14" /><path d="m13 6 6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="composer-foot" style={{ color: palette.muted }}>
        <span>MAI reads widely but isn't always right. Cross-check what matters. Press <kbd>↵</kbd> to send.</span>
      </div>
    </form>);

}

// ---------- Sidebar ----------
function Sidebar({ palette, displayFont, newsFont, threads, activeId, onSelect, onNew, user, onLogout }) {
  const regionLabel = (REGIONS_AUTH.find((r) => r.id === user?.region) || {}).label;
  const initial = (user?.name || 'M').trim().charAt(0).toLowerCase();
  return (
    <aside className="sidebar">
      <div className="side-head">
        <div className="brand">
          <MaiMark palette={palette} size={32} />
          <Wordmark palette={palette} displayFont={displayFont} newsFont={newsFont} size={26} />
        </div>
        <button className="new-btn" onClick={onNew} style={{ color: palette.ink, borderColor: "rgba(0,0,0,0.12)" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
          New
        </button>
      </div>

      <div className="side-section-label" style={{ color: palette.muted }}>Today's threads</div>
      <ul className="thread-list">
        {threads.map((t) =>
        <li key={t.id}>
            <button
            className={`thread-item ${t.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(t.id)}
            style={{ color: palette.ink }}>
            
              <span className="t-title">{t.title}</span>
              <span className="t-time" style={{ color: palette.muted }}>{t.time}</span>
            </button>
          </li>
        )}
      </ul>

      <div className="side-foot" style={{ color: palette.muted, borderColor: "rgba(0,0,0,0.08)" }}>
        <div className="user-row">
          <div className="avatar" style={{ background: palette.accent, color: palette.bg }}>{initial}</div>
          <div className="user-meta">
            <div style={{ color: palette.ink }}>{user?.name || 'Guest'}</div>
            <div>{user?.department || 'No department'}{regionLabel ? ' · ' + regionLabel : ''}</div>
          </div>
          <button className="signout-btn" onClick={onLogout} title="Sign out" aria-label="Sign out" style={{ color: palette.muted }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/></svg>
          </button>
        </div>
      </div>
    </aside>);

}

// ---------- News preferences (aligned with sources.json taxonomy) ----------
const PREF_ROLES = [
  { id: "engineer", label: "For engineers",        note: "Technical depth — model details, code, infra",     defaultDepth: "deep"  },
  { id: "business", label: "For business & sales", note: "Markets, deals, what to tell customers",          defaultDepth: "brief" },
  { id: "legal",    label: "For legal & compliance", note: "Regulation, antitrust, privacy law",            defaultDepth: "brief" },
  { id: "exec",     label: "For executives",       note: "Strategic, high-level signals",                   defaultDepth: "brief" },
  { id: "research", label: "For researchers",      note: "Papers, benchmarks, deep technical reads",        defaultDepth: "deep"  }
];

const TOPIC_GROUPS = [
  {
    id: "topic",
    label: "Technology",
    note: "Core tech beats",
    items: [
      { id: "ai_ml",      label: "AI & ML" },
      { id: "cyber",      label: "Cybersecurity" },
      { id: "cloud",      label: "Cloud & Infrastructure" },
      { id: "softdev",    label: "Software Development" },
      { id: "hardware",   label: "Hardware & Chips" },
      { id: "privacy",    label: "Data & Privacy" },
      { id: "quantum",    label: "Quantum Computing" },
      { id: "robotics",   label: "Robotics & Automation" },
      { id: "fintech",    label: "Fintech & Payments" },
      { id: "health",     label: "Health & Biotech" },
      { id: "cleantech",  label: "Clean Tech & Sustainability" },
      { id: "space",      label: "Space & Satellites" },
      { id: "xr",         label: "Metaverse & XR" }
    ]
  },
  {
    id: "business",
    label: "Business",
    note: "Money, deals, who's hiring",
    items: [
      { id: "ma",         label: "M&A & Funding" },
      { id: "ipo",        label: "IPO & Markets" },
      { id: "bigtech",    label: "Big Tech (FAANG+Microsoft)" },
      { id: "startups",   label: "Startups & Venture" },
      { id: "layoffs",    label: "Layoffs & Hiring" },
      { id: "earnings",   label: "Earnings & Revenue" }
    ]
  },
  {
    id: "regulation",
    label: "Regulation & Policy",
    note: "Rules of the game",
    items: [
      { id: "ai_reg",     label: "AI Regulation" },
      { id: "gdpr",       label: "Data Protection (GDPR, DPDP, LGPD)" },
      { id: "antitrust",  label: "Antitrust & Competition" },
      { id: "exports",    label: "Export Controls & Sanctions" },
      { id: "digiinfra",  label: "Digital Infrastructure Policy" },
      { id: "cyberpol",   label: "Cybersecurity Policy" },
      { id: "platform",   label: "Platform Regulation" }
    ]
  }
];

const PREF_DEPTHS = [
  { id: "deep",  label: "Deep dive", note: "IC level — long-form, technical, with full context" },
  { id: "brief", label: "Brief",     note: "Exec level — short, decision-focused, no jargon" }
];

const PREF_DELIVERY = [
  { id: "daily",    label: "Daily brief",          note: "Every morning, ranked and deduplicated" },
  { id: "weekly",   label: "Weekly digest",        note: "One Sunday long-read of what mattered" },
  { id: "breaking", label: "Breaking-news alerts", note: "Only when your keywords show up" }
];

const PREF_TONES = [
  { id: "calm",      label: "Calm & editorial" },
  { id: "plain",     label: "Plain & direct" },
  { id: "technical", label: "Technical" }
];

function PrefsDeck({ open, onClose, palette, displayFont, newsFont, prefs, setPrefs, onSave, user }) {
  const [step, setStep] = useState(0);
  const bodyRef = useRef(null);
  const steps = ["Role", "Region", "Topics", "Depth", "Delivery", "Voice"];
  useEffect(() => { if (open) setStep(0); }, [open]);
  useEffect(() => { if (bodyRef.current) bodyRef.current.scrollTop = 0; }, [step]);
  if (!open) return null;

  const toggleArr = (key, id) => {
    const arr = prefs[key] || [];
    setPrefs({ ...prefs, [key]: arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id] });
  };
  const setOne = (key, id) => setPrefs({ ...prefs, [key]: id });

  // Role: auto-prefill depth based on role
  const pickRole = (roleId) => {
    const role = PREF_ROLES.find((r) => r.id === roleId);
    setPrefs({ ...prefs, role: roleId, depth: prefs.depth || role.defaultDepth });
  };

  const next = () => setStep((s) => Math.min(s + 1, steps.length - 1));
  const prev = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="prefs-overlay" onClick={onClose}>
      <div className="prefs-deck" onClick={(e) => e.stopPropagation()} style={{ background: palette.bg, color: palette.ink, borderColor: "rgba(0,0,0,0.08)" }}>
        <div className="prefs-grain" style={{ backgroundImage: `url("${grainSvg(0.12)}")` }} />
        <button className="prefs-close" onClick={onClose} aria-label="Close" style={{ color: palette.muted }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>

        <header className="prefs-head">
          <div className="prefs-eyebrow" style={{ color: palette.muted }}>Your reading preferences</div>
          <h2 className="prefs-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
            Tune your <span className="prefs-news" style={{ fontFamily: NEWS_FONTS[newsFont], color: palette.accent }}>news</span>
          </h2>
          <p className="prefs-sub" style={{ color: palette.muted }}>A few quiet choices. MAI uses them to shape every briefing.</p>

          <div className="prefs-stepper">
            {steps.map((s, i) => (
              <button key={s} className={`prefs-step ${i === step ? "active" : ""} ${i < step ? "done" : ""}`} onClick={() => setStep(i)} style={{ color: i === step ? palette.ink : palette.muted }}>
                <span className="prefs-step-num" style={{ borderColor: i === step ? palette.ink : "rgba(0,0,0,0.2)" }}>{String(i+1).padStart(2,"0")}</span>
                <span>{s}</span>
              </button>
            ))}
          </div>
        </header>

        <div className="prefs-body" ref={bodyRef}>
          {step === 0 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>What's your angle on tech?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>I'll match content, depth, and tone to your role. You can override anything later.</div>
              <div className="prefs-radio-col">
                {PREF_ROLES.map((r) => {
                  const on = prefs.role === r.id;
                  return (
                    <button key={r.id} className={`prefs-radio ${on ? "on" : ""}`} onClick={() => pickRole(r.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : "rgba(0,0,0,0.1)", background: on ? palette.cardBg : "rgba(255,253,247,0.4)" }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : "transparent" }} />
                      <div>
                        <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{r.label}</div>
                        <div className="prefs-radio-note" style={{ color: palette.muted }}>{r.note}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>Which region matters most to you?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Pre-filled from your signup. Change anytime — I'll still surface global stories that affect your region.</div>
              <div className="prefs-region-grid">
                {REGIONS_AUTH.map((r) => {
                  const on = (prefs.region || user?.region) === r.id;
                  return (
                    <button key={r.id} className={`prefs-region ${on ? "on" : ""}`} onClick={() => setOne("region", r.id)}
                      style={on
                        ? { background: palette.ink, color: palette.bg, borderColor: palette.ink }
                        : { color: palette.ink, borderColor: "rgba(0,0,0,0.14)", background: "rgba(255,253,247,0.5)" }}>
                      <span>{r.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>What corners of tech matter to you?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Pick as many as you like across three groups. You can change this anytime.</div>
              {TOPIC_GROUPS.map((group) => (
                <div key={group.id} className="prefs-group">
                  <div className="prefs-group-head">
                    <div className="prefs-group-label" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>{group.label}</div>
                    <div className="prefs-group-note" style={{ color: palette.muted }}>{group.note}</div>
                  </div>
                  <div className="prefs-chips">
                    {group.items.map((t) => {
                      const on = (prefs.topics || []).includes(t.id);
                      return (
                        <button key={t.id} className={`prefs-chip ${on ? "on" : ""}`} onClick={() => toggleArr("topics", t.id)}
                          style={on ? { background: palette.ink, color: palette.bg, borderColor: palette.ink } : { color: palette.ink, borderColor: "rgba(0,0,0,0.14)", background: "rgba(255,253,247,0.55)" }}>
                          <span className="prefs-chip-mark">{on ? "✓" : "+"}</span>
                          <span>{t.label}</span>
                        </button>
                      );
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
                  const on = prefs.depth === d.id;
                  return (
                    <button key={d.id} className={`prefs-radio ${on ? "on" : ""}`} onClick={() => setOne("depth", d.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : "rgba(0,0,0,0.1)", background: on ? palette.cardBg : "rgba(255,253,247,0.4)" }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : "transparent" }} />
                      <div>
                        <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{d.label}</div>
                        <div className="prefs-radio-note" style={{ color: palette.muted }}>{d.note}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>When should I bring you the news?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Choose a rhythm. No streaks. No notifications you didn't ask for.</div>
              <div className="prefs-radio-col">
                {PREF_DELIVERY.map((c) => {
                  const on = (prefs.delivery || []).includes(c.id);
                  return (
                    <button key={c.id} className={`prefs-radio ${on ? "on" : ""}`} onClick={() => toggleArr("delivery", c.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : "rgba(0,0,0,0.1)", background: on ? palette.cardBg : "rgba(255,253,247,0.4)" }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : "transparent" }} />
                      <div style={{ flex: 1 }}>
                        <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{c.label}</div>
                        <div className="prefs-radio-note" style={{ color: palette.muted }}>{c.note}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
              {(prefs.delivery || []).includes("breaking") && (
                <div className="prefs-keywords">
                  <label className="prefs-keywords-label" style={{ color: palette.muted }}>Keywords for breaking-news alerts</label>
                  <input type="text" className="prefs-keywords-input"
                    placeholder="GPT-5, Copilot, EU AI Act, NVIDIA, OpenAI…"
                    value={prefs.keywords || ""}
                    onChange={(e) => setPrefs({ ...prefs, keywords: e.target.value })}
                    style={{ color: palette.ink, borderColor: "rgba(0,0,0,0.16)" }} />
                  <p className="prefs-keywords-hint" style={{ color: palette.muted }}>Comma-separated. I'll only ping you when these show up.</p>
                </div>
              )}
            </div>
          )}

          {step === 5 && (
            <div className="prefs-pane">
              <div className="prefs-pane-q" style={{ fontFamily: FONTS[displayFont] }}>What voice suits you?</div>
              <div className="prefs-pane-h" style={{ color: palette.muted }}>Extra personalization — not required, but I'll match your rhythm if you choose.</div>
              <div className="prefs-radio-col">
                {PREF_TONES.map((d) => {
                  const on = prefs.tone === d.id;
                  return (
                    <button key={d.id} className={`prefs-radio ${on ? "on" : ""}`} onClick={() => setOne("tone", d.id)}
                      style={{ color: palette.ink, borderColor: on ? palette.ink : "rgba(0,0,0,0.1)", background: on ? palette.cardBg : "rgba(255,253,247,0.4)" }}>
                      <div className="prefs-radio-dot" style={{ borderColor: palette.ink, background: on ? palette.ink : "transparent" }} />
                      <div className="prefs-radio-label" style={{ fontFamily: FONTS[displayFont] }}>{d.label}</div>
                    </button>
                  );
                })}
              </div>
              <div className="prefs-slider-row">
                <label className="prefs-slider-label" style={{ color: palette.muted }}>Quiet ↔ Lively</label>
                <input type="range" min="0" max="100" value={prefs.energy ?? 35} onChange={(e) => setPrefs({ ...prefs, energy: +e.target.value })} className="prefs-slider" />
              </div>
            </div>
          )}
        </div>

        <footer className="prefs-foot" style={{ borderColor: "rgba(0,0,0,0.08)" }}>
          <button className="prefs-back" onClick={prev} disabled={step === 0} style={{ color: palette.muted }}>← Back</button>
          <div className="prefs-progress" style={{ color: palette.muted }}>{String(step+1).padStart(2,"0")} – {String(steps.length).padStart(2,"0")}</div>
          {step < steps.length - 1 ? (
            <button className="prefs-next" onClick={next} style={{ background: palette.ink, color: palette.bg }}>Continue →</button>
          ) : (
            <button className="prefs-next" onClick={onSave} style={{ background: palette.ink, color: palette.bg }}>Save preferences</button>
          )}
        </footer>
      </div>
    </div>
  );
}

// ---------- Toast ----------
function Toast({ text, onDone }) {
  useEffect(() => {
    if (!text) return;
    const t = setTimeout(onDone, 2200);
    return () => clearTimeout(t);
  }, [text]);
  if (!text) return null;
  return <div className="toast">{text}</div>;
}

// ---------- Microsoft SSO Modal (mock) ----------
const MOCK_MS_ACCOUNTS = [
  { name: 'Eve Sandoval', email: 'eve.sandoval@microsoft.com', department: 'Cloud + AI', region: 'eu', initial: 'e', color: '#0078D4' },
  { name: 'Daniel Kim',   email: 'daniel.kim@microsoft.com',   department: 'Azure',      region: 'na', initial: 'd', color: '#7FBA00' },
  { name: 'Priya Iyer',   email: 'priya.iyer@microsoft.com',   department: 'Research',   region: 'india', initial: 'p', color: '#F25022' }
];

function MicrosoftSSOModal({ open, onClose, onComplete }) {
  // step: 'pick' -> 'password' -> 'stay' -> 'done'
  const [step, setStep] = useState('pick');
  const [account, setAccount] = useState(null);
  const [password, setPassword] = useState('');
  const [pwError, setPwError] = useState('');
  const [otherEmail, setOtherEmail] = useState('');
  const [showOther, setShowOther] = useState(false);

  useEffect(() => {
    if (open) { setStep('pick'); setAccount(null); setPassword(''); setPwError(''); setOtherEmail(''); setShowOther(false); }
  }, [open]);

  if (!open) return null;

  const pickAccount = (acc) => { setAccount(acc); setStep('password'); };

  const useOther = () => {
    const email = otherEmail.trim().toLowerCase();
    if (!/^[^\s@]+@microsoft\.com$/.test(email)) {
      setPwError("Use your @microsoft.com account.");
      return;
    }
    const fallbackName = email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    setAccount({ name: fallbackName, email, department: '', region: '', initial: fallbackName.charAt(0).toLowerCase(), color: '#0078D4' });
    setShowOther(false);
    setStep('password');
  };

  const submitPassword = () => {
    if (!password || password.length < 4) { setPwError("Enter your password."); return; }
    setPwError('');
    setStep('stay');
  };

  const finishStay = (stay) => {
    setStep('done');
    setTimeout(() => {
      onComplete({
        name: account.name,
        email: account.email,
        department: account.department || 'Engineering',
        region: account.region || 'na',
        signedInAt: Date.now(),
        sso: true,
        rememberMe: stay
      });
    }, 700);
  };

  return (
    <div className="ms-overlay" onClick={onClose}>
      <div className="ms-card" onClick={(e) => e.stopPropagation()}>
        <button className="ms-close" onClick={onClose} aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>

        <div className="ms-logo-row">
          <svg width="108" height="23" viewBox="0 0 108 23" aria-label="Microsoft">
            <rect x="0" y="0" width="10" height="10" fill="#F25022"/>
            <rect x="11" y="0" width="10" height="10" fill="#7FBA00"/>
            <rect x="0" y="11" width="10" height="10" fill="#00A4EF"/>
            <rect x="11" y="11" width="10" height="10" fill="#FFB900"/>
            <text x="28" y="16" fill="#5E5E5E" style={{fontFamily:"Segoe UI, system-ui, sans-serif", fontSize:"13px", fontWeight:600}}>Microsoft</text>
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
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#107C10" strokeWidth="2"><path d="M20 6L9 17l-5-5"/></svg>
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
            <button className="ms-back" onClick={() => { setShowOther(false); setPwError(''); }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            </button>
            <h3 className="ms-h">Sign in</h3>
            <label className="ms-field">
              <span>Email, phone, or Skype</span>
              <input type="email" value={otherEmail} onChange={(e) => setOtherEmail(e.target.value)}
                placeholder="someone@microsoft.com" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') useOther(); }} />
            </label>
            {pwError && <div className="ms-error">{pwError}</div>}
            <p className="ms-note">No account? <a href="#" onClick={(e) => e.preventDefault()}>Create one!</a></p>
            <div className="ms-actions">
              <button className="ms-primary" onClick={useOther}>Next</button>
            </div>
          </>
        )}

        {step === 'password' && account && (
          <>
            <button className="ms-back" onClick={() => setStep('pick')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
              <span className="ms-back-email">{account.email}</span>
            </button>
            <h3 className="ms-h">Enter password</h3>
            <label className="ms-field">
              <span>Password</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Password" autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') submitPassword(); }} />
            </label>
            {pwError && <div className="ms-error">{pwError}</div>}
            <a href="#" className="ms-link" onClick={(e) => e.preventDefault()}>Forgot password?</a>
            <div className="ms-actions">
              <button className="ms-primary" onClick={submitPassword}>Sign in</button>
            </div>
          </>
        )}

        {step === 'stay' && account && (
          <>
            <h3 className="ms-h">Stay signed in?</h3>
            <p className="ms-body">Do this to reduce the number of times you are asked to sign in.</p>
            <label className="ms-check">
              <input type="checkbox" /> <span>Don't show this again</span>
            </label>
            <div className="ms-actions ms-actions-row">
              <button className="ms-secondary" onClick={() => finishStay(false)}>No</button>
              <button className="ms-primary" onClick={() => finishStay(true)}>Yes</button>
            </div>
          </>
        )}

        {step === 'done' && account && (
          <div className="ms-done">
            <div className="ms-spinner" />
            <p className="ms-body">Signing you in to MAI…</p>
          </div>
        )}

        <div className="ms-foot">
          <a href="#" onClick={(e) => e.preventDefault()}>Terms of use</a>
          <a href="#" onClick={(e) => e.preventDefault()}>Privacy & cookies</a>
        </div>
      </div>
    </div>
  );
}

// ---------- Auth Gate ----------
function AuthGate({ palette, displayFont, newsFont, blur, grain, onAuthed, mode, setMode }) {
  const [form, setForm] = useState({ email: '', password: '', name: '', department: '', region: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ssoOpen, setSsoOpen] = useState(false);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const validateCorporateEmail = (email) => {
    const e = String(email || '').trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return "Enter a valid email address.";
    if (!e.endsWith('@' + CORPORATE_DOMAIN)) return `Use your corporate email (@${CORPORATE_DOMAIN}).`;
    return null;
  };

  const submit = (e) => {
    e.preventDefault();
    setError('');
    const emailErr = validateCorporateEmail(form.email);
    if (emailErr) return setError(emailErr);
    if (!form.password || form.password.length < 6) return setError("Password must be at least 6 characters.");

    if (mode === 'signup') {
      if (!form.name.trim()) return setError("Please enter your name.");
      if (!form.department) return setError("Please choose your department.");
      if (!form.region) return setError("Please choose your region.");
    }

    setLoading(true);
    setTimeout(() => {
      const fallbackName = form.email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      const user = {
        name: form.name.trim() || fallbackName,
        email: form.email.trim().toLowerCase(),
        department: form.department || 'Engineering',
        region: form.region || 'eu',
        signedInAt: Date.now()
      };
      writeSession(user);
      setLoading(false);
      onAuthed(user);
    }, 500);
  };

  const ssoSignin = () => { setSsoOpen(true); };

  const completeSso = (user) => {
    writeSession(user);
    setSsoOpen(false);
    onAuthed(user);
  };

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
            Tech news,<br/><em>made yours.</em>
          </h1>
          <div className="auth-bullets" style={{ color: palette.muted }}>
            <p className="auth-line">Tech moves too fast. MAI personalizes the news to your preferences and sends it your way.</p>
            <p className="auth-line">Want to know more? Chat with me — I'll dig deeper, with sources.</p>
          </div>
        </div>

        <div className="auth-card-col">
        <div className="auth-card" style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.08)' }}>
          <div className="auth-tabs">
            <button type="button" className={`auth-tab ${mode === 'signin' ? 'on' : ''}`}
              onClick={() => { setMode('signin'); setError(''); }}
              style={mode === 'signin'
                ? { color: palette.ink, borderBottomColor: palette.ink }
                : { color: palette.muted, borderBottomColor: 'transparent' }}>
              Sign in
            </button>
            <button type="button" className={`auth-tab ${mode === 'signup' ? 'on' : ''}`}
              onClick={() => { setMode('signup'); setError(''); }}
              style={mode === 'signup'
                ? { color: palette.ink, borderBottomColor: palette.ink }
                : { color: palette.muted, borderBottomColor: 'transparent' }}>
              Create account
            </button>
          </div>

          <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
            {mode === 'signin' ? 'Welcome back.' : <>Get your first <span style={{ fontFamily: NEWS_FONTS[newsFont], fontStyle: 'italic', fontWeight: 600, color: palette.accent }}>briefing</span>.</>}
          </h2>
          <p className="auth-sub" style={{ color: palette.muted }}>
            {mode === 'signin'
              ? 'Use your Microsoft corporate account to continue.'
              : 'A few quiet details. Then MAI shapes the news around you.'}
          </p>

          <button type="button" className="auth-sso" onClick={ssoSignin} disabled={loading}
            style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)', background: 'rgba(255,253,247,0.6)' }}>
            <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
              <rect x="1" y="1" width="9" height="9" fill="#F25022"/>
              <rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>
              <rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>
              <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
            </svg>
            <span>Continue with Microsoft</span>
          </button>

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
              <span className="auth-hint" style={{ color: palette.muted }}>Must be your @{CORPORATE_DOMAIN} address.</span>
            </label>

            {mode === 'signup' && (
              <>
                <label className="auth-field">
                  <span style={{ color: palette.muted }}>Department</span>
                  <select value={form.department} onChange={(e) => update('department', e.target.value)}
                    style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }}>
                    <option value="">Choose your department…</option>
                    {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </label>
                <div className="auth-field">
                  <span style={{ color: palette.muted }}>Region</span>
                  <div className="auth-region-grid">
                    {REGIONS_AUTH.map((r) => {
                      const on = form.region === r.id;
                      return (
                        <button type="button" key={r.id} className={`auth-region ${on ? 'on' : ''}`}
                          onClick={() => update('region', r.id)}
                          style={on
                            ? { background: palette.ink, color: palette.bg, borderColor: palette.ink }
                            : { color: palette.ink, borderColor: 'rgba(0,0,0,0.14)', background: 'rgba(255,253,247,0.5)' }}>
                          {r.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            <label className="auth-field">
              <span style={{ color: palette.muted }}>Password</span>
              <input type="password" value={form.password} onChange={(e) => update('password', e.target.value)}
                placeholder="••••••••" autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }} />
            </label>

            {mode === 'signin' && (
              <div className="auth-row-between">
                <label className="auth-check" style={{ color: palette.muted }}>
                  <input type="checkbox" /> <span>Remember me</span>
                </label>
                <button type="button" className="auth-link" style={{ color: palette.accent }}>Forgot password?</button>
              </div>
            )}

            {error && <div className="auth-error" style={{ color: palette.ink }}>{error}</div>}

            <button type="submit" className="auth-submit" disabled={loading}
              style={{ background: palette.ink, color: palette.bg }}>
              {loading ? 'Just a moment…' : (mode === 'signin' ? 'Sign in →' : 'Create account →')}
            </button>
          </form>

          <p className="auth-meta" style={{ color: palette.muted }}>
            By continuing you agree to MAI's terms and Microsoft's internal data-handling policies. We never send breaking-news alerts you haven't asked for.
          </p>
        </div>
        </div>
      </div>

      <MicrosoftSSOModal open={ssoOpen} onClose={() => setSsoOpen(false)} onComplete={completeSso} />
    </div>
  );
}

function App() {
  const [tw, setTweak] = useTweaks(TWEAKS_DEFAULTS);
  const palette = PALETTES[tw.palette] || PALETTES.moss;
  const [user, setUser] = useState(() => readSession());
  const [authMode, setAuthMode] = useState('signin');
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [prefs, setPrefs] = useState({
    role: "engineer",
    region: user?.region || "eu",
    topics: ["ai_ml", "cloud", "cyber"],
    depth: "deep",
    delivery: ["daily"],
    keywords: "",
    tone: "calm",
    energy: 35,
  });

  const [threads, setThreads] = useState([
  { id: "t1", title: "Latest LLM benchmarks", time: "Now" },
  { id: "t2", title: "Frontier releases this week", time: "Today" },
  { id: "t3", title: "Open vs. closed models", time: "Yesterday" },
  { id: "t4", title: "AI policy in the EU", time: "Mon" },
  { id: "t5", title: "What I missed last week", time: "Apr 28" }]
  );
  const [activeId, setActiveId] = useState("t1");
  const [messages, setMessages] = useState(tw.preloadDemo ? buildBenchmarkConvo() : []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const scrollRef = useRef(null);

  const isEmpty = messages.length === 0;

  useEffect(() => {
    const el = scrollRef.current;if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function buildBenchmarkConvo() {
    return [
    { id: 1, role: "user", content: "What are the latest LLM benchmarks?" },
    {
      id: 2,
      role: "ai",
      content:
      `a few things are stirring in benchmark-land this week — none of it dramatic, but the picture is shifting.

the headline is that no single model is sweeping anymore. GPT-5.1 leads on reasoning and code; Claude 4.5 still owns long-context recall and tool-use; Gemini 3 is closer than it's been in months. on the open side, Llama 4.1 just cracked the Arena top five for the first time.

the more interesting story underneath: MMLU-Pro is saturating — five models cluster within two points — and researchers are openly arguing it's time for harder evals. SWE-bench Verified jumped after a new tool-use protocol, which says more about plumbing than raw intelligence.`,
      cards: BENCHMARK_CARDS
    }];

  }

  const send = async (overrideText) => {
    const text = (overrideText ?? input).trim();
    if (!text || busy) return;
    setInput("");
    const userMsg = { id: Date.now(), role: "user", content: text };
    const thinkingId = Date.now() + 1;
    setMessages((m) => [...m, userMsg, { id: thinkingId, role: "ai", thinking: true }]);
    setBusy(true);

    if (messages.length === 0) {
      setThreads((ts) => {
        const newTitle = text.length > 40 ? text.slice(0, 40) + "…" : text;
        return ts.map((t) => t.id === activeId ? { ...t, title: newTitle, time: "Just now" } : t);
      });
    }

    try {
      const reply = await window.claude.complete({
        messages: [
        { role: "user", content:
          `You are MAI news — a calm, editorial AI-news companion. You ONLY discuss artificial intelligence: models, benchmarks, research papers, releases, policy, infrastructure, the people and companies behind it. If asked about anything outside AI, gently redirect.

Voice: thoughtful, literary, unhurried. Lowercase is fine. No emoji. No bullet lists unless explicitly asked. Keep replies to 2–4 short paragraphs.

Name the story plainly, give context, surface multiple perspectives where relevant, end with one open question or angle worth exploring next. If you don't know recent specifics, say so honestly.

Begin without preamble.

User: ${text}` }]

      });
      setMessages((m) => m.map((msg) => msg.id === thinkingId ? { id: thinkingId, role: "ai", content: reply } : msg));
    } catch (err) {
      setMessages((m) => m.map((msg) => msg.id === thinkingId ? { id: thinkingId, role: "ai", content: "i'm having trouble reaching my thoughts right now. try again in a moment." } : msg));
    } finally {
      setBusy(false);
    }
  };

  const startNew = () => {
    const id = "t" + Date.now();
    setThreads((ts) => [{ id, title: "New conversation", time: "Now" }, ...ts]);
    setActiveId(id);
    setMessages([]);
  };

  const handleAction = (kind, card) => {
    if (kind === "read") setToast(`Opening ${card.source}…`);
    if (kind === "more") setToast(`Pulling threads on "${card.tag}"…`);
  };
  const handleActionChip = (a) => {
    const map = {
      report: "Drafting a one-page report from these stories…",
      compare: "Building a side-by-side comparison…",
      explore: "Surfacing related papers and releases…",
      save: "Saved to your library."
    };
    setToast(map[a.id] || a.label);
  };

  if (!user) {
    return (
      <>
        <AuthGate
          palette={palette}
          displayFont={tw.displayFont}
          newsFont={tw.newsFont}
          blur={tw.blur}
          grain={tw.grain}
          mode={authMode}
          setMode={setAuthMode}
          onAuthed={(u) => setUser(u)}
        />
        <TweaksPanel title="Tweaks">
          <TweakSection title="Mood">
            <TweakSelect label="Palette" value={tw.palette} onChange={(v) => setTweak("palette", v)}
              options={Object.entries(PALETTES).map(([k, v]) => ({ value: k, label: v.name }))} />
            <TweakSelect label="Display font" value={tw.displayFont} onChange={(v) => setTweak("displayFont", v)}
              options={Object.keys(FONTS).map((k) => ({ value: k, label: k }))} />
            <TweakSelect label="'news' font" value={tw.newsFont} onChange={(v) => setTweak("newsFont", v)}
              options={Object.keys(NEWS_FONTS).map((k) => ({ value: k, label: k }))} />
          </TweakSection>
          <TweakSection title="Atmosphere">
            <TweakSlider label="Grain" min={0} max={0.5} step={0.01} value={tw.grain} onChange={(v) => setTweak("grain", v)} />
            <TweakSlider label="Blur" min={20} max={140} step={1} value={tw.blur} onChange={(v) => setTweak("blur", v)} />
          </TweakSection>
        </TweaksPanel>
      </>
    );
  }

  return (
    <div className="shell" style={{ color: palette.ink, fontFamily: "'Inter Tight', system-ui, sans-serif" }}>
      <Backdrop palette={palette} blur={tw.blur} grain={tw.grain} />

      <Sidebar
        palette={palette}
        displayFont={tw.displayFont}
        newsFont={tw.newsFont}
        threads={threads}
        activeId={activeId}
        onSelect={(id) => {setActiveId(id);if (id !== "t1") setMessages([]);else setMessages(buildBenchmarkConvo());}}
        onNew={startNew}
        user={user}
        onLogout={() => { writeSession(null); setUser(null); }} />
      

      <main className="main">
        <header className="topbar">
          <div className="crumb" style={{ color: palette.muted }}>
            <span className="crumb-tag" style={{ borderColor: "rgba(0,0,0,0.1)" }}>AI · Benchmarks</span>
            <span className="crumb-title" style={{ color: palette.ink }}>{threads.find((t) => t.id === activeId)?.title || "Conversation"}</span>
          </div>
          <div className="topbar-right" style={{ color: palette.muted }}>
            <button className="ghost-btn" onClick={() => setPrefsOpen(true)}>Preferences</button>
            <button className="ghost-btn">Sources</button>
            <button className="ghost-btn">Save</button>
            <button className="ghost-btn">Share</button>
          </div>
        </header>

        <section className="canvas" ref={scrollRef}>
          {isEmpty ?
          <div className="hero">
              <div className="hero-eyebrow" style={{ color: palette.muted }}>Good afternoon, Eve.</div>
              <h1 className="hero-title" style={{ fontFamily: FONTS[tw.displayFont], color: palette.ink }}>
                Explore AI <span className="hero-news" style={{ fontFamily: NEWS_FONTS[tw.newsFont], color: palette.accent }}>news</span>
              </h1>
              <p className="hero-sub" style={{ color: palette.muted }}>{tw.tagline}</p>

              {tw.showSuggestions &&
            <div className="chips">
                  {SUGGESTIONS.map((s) =>
              <button
                key={s.label}
                className="chip"
                onClick={() => send(s.prompt)}
                style={{ color: palette.ink, borderColor: "rgba(0,0,0,0.12)", background: "rgba(255,253,247,0.55)" }}>
                
                      {s.label}
                    </button>
              )}
                </div>
            }
            </div> :

          <div className="thread">
              {messages.map((m) =>
            <Message
              key={m.id}
              msg={m}
              palette={palette}
              displayFont={tw.displayFont}
              compact={tw.compactMessages}
              onAction={handleAction}
              onActionChip={handleActionChip}
              onFollowup={(f) => send(f)} />

            )}
            </div>
          }
        </section>

        <div className="composer-wrap">
          <Composer value={input} setValue={setInput} onSend={() => send()} palette={palette} disabled={busy} />
        </div>
      </main>

      <Toast text={toast} onDone={() => setToast("")} />

      <PrefsDeck
        open={prefsOpen}
        onClose={() => setPrefsOpen(false)}
        palette={palette}
        displayFont={tw.displayFont}
        newsFont={tw.newsFont}
        prefs={prefs}
        setPrefs={setPrefs}
        user={user}
        onSave={() => { setPrefsOpen(false); setToast("Preferences saved. I'll keep these in mind."); }}
      />

      <TweaksPanel title="Tweaks">
        <TweakSection title="Mood">
          <TweakSelect label="Palette" value={tw.palette} onChange={(v) => setTweak("palette", v)}
          options={Object.entries(PALETTES).map(([k, v]) => ({ value: k, label: v.name }))} />
          <TweakSelect label="Display font" value={tw.displayFont} onChange={(v) => setTweak("displayFont", v)}
          options={Object.keys(FONTS).map((k) => ({ value: k, label: k }))} />
          <TweakSelect label="'news' font" value={tw.newsFont} onChange={(v) => setTweak("newsFont", v)}
          options={Object.keys(NEWS_FONTS).map((k) => ({ value: k, label: k }))} />
        </TweakSection>
        <TweakSection title="Atmosphere">
          <TweakSlider label="Grain" min={0} max={0.5} step={0.01} value={tw.grain} onChange={(v) => setTweak("grain", v)} />
          <TweakSlider label="Blur" min={20} max={140} step={1} value={tw.blur} onChange={(v) => setTweak("blur", v)} />
        </TweakSection>
        <TweakSection title="Layout">
          <TweakToggle label="Show suggestions" value={tw.showSuggestions} onChange={(v) => setTweak("showSuggestions", v)} />
          <TweakToggle label="Compact messages" value={tw.compactMessages} onChange={(v) => setTweak("compactMessages", v)} />
          <TweakText label="Tagline" value={tw.tagline} onChange={(v) => setTweak("tagline", v)} />
        </TweakSection>
      </TweaksPanel>
    </div>);

}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);