'use client'

import NewsCard from '@/components/news/NewsCard'
import { FONTS } from '@/constants/fonts'
import type { NewsCard as NewsCardType, Palette } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  savedArticles: NewsCardType[]
  savedIds: Set<string>
  onToggleSave: (card: NewsCardType) => void
  onAction: (kind: string, card: NewsCardType) => void
}

export default function SavedView({ palette, displayFont, savedArticles, savedIds, onToggleSave, onAction }: Props) {
  return (
    <div className="saved-view">
      <div className="saved-header">
        <div className="saved-eyebrow" style={{ color: palette.muted }}>Library</div>
        <h2 className="saved-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
          Saved articles
        </h2>
        <p className="saved-sub" style={{ color: palette.muted }}>
          {savedArticles.length === 0
            ? 'No articles saved yet. Bookmark any story from your briefings.'
            : `${savedArticles.length} article${savedArticles.length !== 1 ? 's' : ''} saved across your folders.`}
        </p>
      </div>

      {savedArticles.length > 0 && (
        <div className="saved-grid">
          {savedArticles.map((card) => (
            <NewsCard
              key={card.id}
              card={card}
              palette={palette}
              saved={savedIds.has(card.id)}
              onToggleSave={onToggleSave}
              onAction={onAction}
            />
          ))}
        </div>
      )}

      {savedArticles.length === 0 && (
        <div className="saved-empty" style={{ color: palette.muted }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
          </svg>
          <p>Open a briefing and tap the bookmark icon on any article.</p>
        </div>
      )}
    </div>
  )
}
