'use client'

import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { TOPIC_GROUPS } from '@/constants/preferences'
import type { Palette, Prefs, User } from '@/types'

const MOCK_ARTICLES: Record<string, { source: string; time: string; title: string; blurb: string }[]> = {
  ai_ml: [
    { source: 'VentureBeat', time: '1h ago', title: 'OpenAI ships GPT-5 with extended thinking and real-time web grounding', blurb: 'The new model adds a "deep research" mode that chains searches before answering, cutting hallucination rates on factual queries by an estimated 40%.' },
    { source: 'MIT Technology Review', time: '3h ago', title: "Anthropic's Claude 4.5 tops long-context benchmarks by wide margin", blurb: 'In internal evals shared with researchers, Claude 4.5 processes one million tokens with near-perfect recall — a threshold no rival has matched in blind tests.' },
  ],
  cyber: [
    { source: 'The Register', time: '2h ago', title: 'Critical zero-day in Ivanti VPN actively exploited by state-linked group', blurb: 'CISA issued an emergency directive after confirming exploitation of CVE-2026-2241. Patches are available; agencies have 48 hours to apply them.' },
    { source: 'Wired', time: '5h ago', title: 'Salt Typhoon returns: new campaign targets telecoms in three EU countries', blurb: "Researchers at Mandiant linked fresh infrastructure to the Chinese APT group responsible for last year's US carrier breaches." },
  ],
  cloud: [
    { source: 'AWS Blog', time: '4h ago', title: 'Amazon Bedrock adds agent memory and cross-region inference routing', blurb: 'New primitives let developers build agents that persist context across sessions and automatically route requests to the lowest-latency region.' },
    { source: 'GeekWire', time: '6h ago', title: 'Microsoft Azure Arc expands to 12 new sovereign cloud regions', blurb: 'The expansion targets government and financial customers in EMEA and APAC who face strict data-residency requirements.' },
  ],
  hardware: [
    { source: 'NVIDIA Blog', time: '2h ago', title: 'NVIDIA Blackwell Ultra ships to hyperscalers — 2.5× inference throughput over H100', blurb: 'The B200 Ultra delivers 20 petaflops of FP4 compute per chip. Microsoft, Google, and Oracle are first in line for the new hardware.' },
    { source: 'TechCrunch', time: '8h ago', title: 'TSMC confirms 2nm volume production on track for Q3 2026', blurb: 'The Hsinchu fab will initially serve Apple and NVIDIA. Yield rates are reportedly above 70%, ahead of internal targets for this stage.' },
  ],
  ai_reg: [
    { source: 'Euractiv', time: '3h ago', title: 'EU AI Act enforcement body publishes first binding guidelines on GPAI models', blurb: 'The AI Office technical guidance clarifies what systematic risk means for general-purpose AI providers — triggering new audit obligations for six named models.' },
    { source: 'Tech Policy Press', time: '5h ago', title: 'US Senate committee advances bipartisan AI liability framework', blurb: 'The draft bill would create a tiered liability system: developers bear strict liability for harm caused by high-risk systems, with a safe-harbor carve-out for audited models.' },
  ],
  bigtech: [
    { source: 'Reuters Technology', time: '1h ago', title: 'Microsoft Q3 earnings: Azure grows 33% YoY, Copilot MAUs cross 100 million', blurb: 'CEO Satya Nadella called it "the quarter AI became a revenue engine, not a cost center." Operating income beat estimates by $1.2bn.' },
    { source: 'Bloomberg Technology', time: '4h ago', title: 'Google DeepMind merges with Google Brain under new unified research org', blurb: 'The combined team of 4,000 researchers will be led by Demis Hassabis and report directly to Sundar Pichai, signalling a deeper integration of AI into core products.' },
  ],
  startups: [
    { source: 'TechCrunch', time: '2h ago', title: 'Mistral raises €600M Series C at €6bn valuation to take on OpenAI in Europe', blurb: 'The round, led by General Catalyst, will fund a new Paris datacenter and expansion of the enterprise API platform into 14 new markets.' },
    { source: 'Sifted', time: '6h ago', title: 'CEE AI startups attracted record €1.4bn in 2025 — Poland and Romania lead', blurb: 'A new report from The Recursive shows Central and Eastern Europe is the fastest-growing AI startup cluster outside London and Paris.' },
  ],
  gdpr: [
    { source: 'EDPB', time: '1d ago', title: 'EDPB issues urgent opinion on AI-generated synthetic personal data under GDPR', blurb: 'The board ruled that synthetic data derived from personal data retains GDPR protections unless re-identification risk falls below a defined statistical threshold.' },
    { source: 'Silicon Republic', time: '8h ago', title: "Ireland's DPC fines Meta EUR310M over cross-border data transfers to US servers", blurb: "The decision follows a two-year investigation and applies to Instagram's ad-targeting pipeline. Meta has 3 months to comply or face daily penalties." },
  ],
  health: [
    { source: 'STAT News', time: '3h ago', title: "Google DeepMind's AlphaFold 4 predicts protein-drug interactions with 91% accuracy", blurb: 'The latest version extends beyond structure prediction to binding affinity estimation — a capability that could shorten drug discovery timelines by years.' },
    { source: 'MIT Technology Review', time: '7h ago', title: 'FDA clears first AI-only diagnostic for diabetic retinopathy without physician review', blurb: "IDx-DR's successor model becomes the first autonomous AI diagnostic cleared for routine clinical deployment in the US, no ophthalmologist required." },
  ],
}

function getTopicLabel(id: string): string {
  for (const g of TOPIC_GROUPS) {
    const item = g.items.find((t) => t.id === id)
    if (item) return item.label
  }
  return id
}

function formatDate(): string {
  return new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  prefs: Prefs
  user: User
  onAsk: (q: string) => void
}

export default function BriefingPreview({ palette, displayFont, newsFont, prefs, user, onAsk }: Props) {
  const topics = prefs.topics && prefs.topics.length > 0 ? prefs.topics.slice(0, 4) : ['ai_ml', 'bigtech', 'ai_reg', 'hardware']
  const deliveryLabel = (prefs.delivery?.[0] === 'weekly') ? 'Weekly digest' : 'Daily brief'

  return (
    <div className="briefing-wrap">
      <div className="briefing-header">
        <div className="briefing-eyebrow" style={{ color: palette.muted }}>
          {deliveryLabel} · {formatDate()}
        </div>
        <h1 className="briefing-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
          Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 18 ? 'afternoon' : 'evening'},{' '}
          <span style={{ fontFamily: NEWS_FONTS[newsFont], fontStyle: 'italic', color: palette.accent }}>
            {user.name.split(' ')[0]}.
          </span>
        </h1>
        <p className="briefing-sub" style={{ color: palette.muted }}>
          Here's what's moving in your topics today. Click any story to go deeper.
        </p>
      </div>

      <div className="briefing-sections">
        {topics.map((topicId) => {
          const articles = MOCK_ARTICLES[topicId]
          if (!articles) return null
          return (
            <div key={topicId} className="briefing-section">
              <div className="briefing-section-label" style={{ color: palette.accent, borderColor: palette.accent }}>
                {getTopicLabel(topicId)}
              </div>
              <div className="briefing-cards">
                {articles.map((a, i) => (
                  <button key={i} className="briefing-card" onClick={() => onAsk(`Tell me more about: ${a.title}`)}
                    style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.07)', color: palette.ink }}>
                    <div className="briefing-card-meta" style={{ color: palette.muted }}>
                      <span>{a.source}</span>
                      <span>·</span>
                      <span>{a.time}</span>
                    </div>
                    <div className="briefing-card-title" style={{ fontFamily: FONTS[displayFont] }}>{a.title}</div>
                    <div className="briefing-card-blurb" style={{ color: palette.muted }}>{a.blurb}</div>
                    <div className="briefing-card-cta" style={{ color: palette.accent }}>Ask MAI to go deeper →</div>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
