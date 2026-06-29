'use client'

import { useState, useEffect } from 'react'
import { listArticles, type ApiArticle } from '@/lib/api'
import { FONTS } from '@/constants/fonts'
import type { Palette } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  userTopics?: string[]
  onAsk: (q: string) => void
}

const TOPIC_LABELS: Record<string, string> = {
  artificial_intelligence_ml: 'AI & ML',
  ai_tools_productivity: 'Dev Tools',
  software_development: 'Software',
  cloud_infrastructure: 'Cloud',
  hardware_chips: 'Hardware',
  cybersecurity: 'Security',
  health_biotech: 'Biotech',
  metaverse_xr: 'XR',
  quantum_computing: 'Quantum',
  fintech: 'Fintech',
  robotics: 'Robotics',
  sustainability_tech: 'Sustainability',
  media_entertainment: 'Media',
  enterprise_software: 'Enterprise',
  policy_regulation: 'Policy',
}

function labelForSlug(slug: string): string {
  if (TOPIC_LABELS[slug]) return TOPIC_LABELS[slug]
  return slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function relativeTime(isoStr: string): string {
  const d = new Date(isoStr)
  const diffMs = Date.now() - d.getTime()
  const h = Math.floor(diffMs / 3600000)
  if (h < 1) return 'Just now'
  if (h < 24) return `${h}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

interface CardProps {
  article: ApiArticle
  onAsk: (q: string) => void
  palette: Palette
  displayFont: string
  variant: 'featured' | 'side' | 'grid'
}

function ArticleCard({ article, onAsk, palette, displayFont, variant }: CardProps) {
  const [hovered, setHovered] = useState(false)
  const [imgError, setImgError] = useState(false)
  const isFeatured = variant === 'featured'
  const isSide = variant === 'side'
  const hasImage = Boolean(article.image_url) && !imgError

  return (
    <div
      className={`dash2-card${isFeatured ? ' dash2-card--featured' : ''}${isSide ? ' dash2-card--side' : ''}${hasImage ? ' dash2-card--has-img' : ''}`}
      style={{
        background: hovered ? palette.cardBg : 'rgba(255,253,247,0.38)',
        borderColor: hovered ? 'rgba(0,0,0,0.13)' : 'rgba(0,0,0,0.07)',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Text content — always left/main column */}
      <div className="dash2-card-body">
        <div className="dash2-card-head">
          <span className="dash2-source" style={{ color: palette.accent }}>
            {article.source.toUpperCase()}
          </span>
          <span className="dash2-time" style={{ color: palette.muted }}>
            {article.published_at ? relativeTime(article.published_at) : ''}
          </span>
        </div>

        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className={`dash2-card-title${isFeatured ? ' dash2-card-title--featured' : ''}${isSide ? ' dash2-card-title--side' : ''}`}
          style={{ fontFamily: FONTS[displayFont], color: palette.ink }}
        >
          {article.title}
        </a>

        {article.extract && !isSide && (
          <p
            className={`dash2-card-extract${isFeatured ? ' dash2-card-extract--featured' : ''}`}
            style={{ color: palette.muted }}
          >
            {article.extract}
          </p>
        )}

        <div className="dash2-card-foot">
          <div className="dash2-topics">
            {article.topics.slice(0, isFeatured ? 3 : 2).map((t) => (
              <span
                key={t}
                className="dash2-topic-pill"
                style={{ background: 'rgba(0,0,0,0.055)', color: palette.muted }}
              >
                {labelForSlug(t)}
              </span>
            ))}
          </div>
          <button
            className="dash2-ask-btn"
            onClick={() => onAsk(`Tell me more about: ${article.title}`)}
            style={{
              color: hovered ? palette.accent : 'transparent',
              borderColor: hovered ? palette.accent : 'transparent',
            }}
          >
            Ask MAI →
          </button>
        </div>
      </div>

      {/* Image panel — right side, ~30% width, bleeds to card edge */}
      {hasImage && (
        <div className="dash2-card-img-panel">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={article.image_url!}
            alt=""
            loading="lazy"
            onError={() => setImgError(true)}
          />
        </div>
      )}
    </div>
  )
}

function Skeleton({ palette }: { palette: Palette }) {
  const shim = { background: `${palette.muted}18` }
  return (
    <div className="dash2-bento">
      <div className="dash2-skel-featured" style={shim} />
      <div className="dash2-side-grid">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="dash2-skel-card" style={{ ...shim, animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
    </div>
  )
}

export default function DashboardView({ palette, displayFont, userTopics, onAsk }: Props) {
  const [allArticles, setAllArticles] = useState<ApiArticle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('all')

  const topicsKey = (userTopics ?? []).join(',')

  // Fetch once per user-preference change; tab switching filters in memory
  useEffect(() => {
    setLoading(true)
    setError('')
    const filterTopics = userTopics?.length ? userTopics : undefined
    listArticles({ limit: 50, topics: filterTopics })
      .then(setAllArticles)
      .catch((e: Error) => setError(e?.message ?? 'Could not load articles.'))
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicsKey])

  const tabFiltered =
    activeTab === 'all'
      ? allArticles
      : allArticles.filter((a) => a.topics.includes(activeTab))

  // Dashboard only shows articles that have an image
  const articles = tabFiltered.filter((a) => a.image_url)

  // Derive tabs from all fetched articles (include articles without images for counts)
  const topicCounts = allArticles.reduce<Record<string, number>>((acc, a) => {
    a.topics.forEach((t) => { acc[t] = (acc[t] ?? 0) + 1 })
    return acc
  }, {})
  const topTabs = Object.entries(topicCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([slug]) => slug)

  const dateStr = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  })

  const featured = articles[0]
  const sideCards = articles.slice(1, 3)
  const gridCards = articles.slice(3, 6)

  return (
    <div className="dash2-wrap">
      {/* Header */}
      <div className="dash2-header">
        <p className="dash2-date" style={{ color: palette.muted }}>{dateStr}</p>
        <h1 className="dash2-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
          Today&apos;s Intelligence
        </h1>
      </div>

      {/* Topic tabs */}
      {topTabs.length > 0 && (
        <div className="dash2-tabs">
          <button
            className={`dash2-tab${activeTab === 'all' ? ' dash2-tab--active' : ''}`}
            onClick={() => setActiveTab('all')}
            style={{
              color: activeTab === 'all' ? palette.ink : palette.muted,
              borderBottomColor: activeTab === 'all' ? palette.accent : 'transparent',
            }}
          >
            All
          </button>
          {topTabs.map((slug) => (
            <button
              key={slug}
              className={`dash2-tab${activeTab === slug ? ' dash2-tab--active' : ''}`}
              onClick={() => setActiveTab(slug)}
              style={{
                color: activeTab === slug ? palette.ink : palette.muted,
                borderBottomColor: activeTab === slug ? palette.accent : 'transparent',
              }}
            >
              {labelForSlug(slug)}
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && <Skeleton palette={palette} />}

      {/* Error */}
      {!loading && error && (
        <p className="dash2-empty" style={{ color: palette.muted }}>{error}</p>
      )}

      {/* Empty */}
      {!loading && !error && articles.length === 0 && (
        <p className="dash2-empty" style={{ color: palette.muted }}>
          No articles yet — run ingest first.
        </p>
      )}

      {/* Content: 2-row bento — (featured + 2 side) then (3 equal) */}
      {!loading && featured && (
        <div className="dash2-content">
          <div className="dash2-bento">
            <ArticleCard article={featured} onAsk={onAsk} palette={palette} displayFont={displayFont} variant="featured" />
            {sideCards.length > 0 && (
              <div className="dash2-side-col">
                {sideCards.map((a) => (
                  <ArticleCard key={a.id} article={a} onAsk={onAsk} palette={palette} displayFont={displayFont} variant="side" />
                ))}
              </div>
            )}
          </div>

          {gridCards.length > 0 && (
            <div className="dash2-grid">
              {gridCards.map((a) => (
                <ArticleCard key={a.id} article={a} onAsk={onAsk} palette={palette} displayFont={displayFont} variant="grid" />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
