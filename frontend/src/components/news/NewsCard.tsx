'use client'

import Icon from '@/components/ui/Icon'
import type { NewsCard as NewsCardType, Palette } from '@/types'

interface Props {
  card: NewsCardType
  palette: Palette
  onAction: (kind: string, card: NewsCardType) => void
}

export default function NewsCard({ card, palette, onAction }: Props) {
  const isLead = card.tone === 'lead'
  return (
    <article
      className={`ncard ${isLead ? 'ncard-lead' : ''}`}
      style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.07)', color: palette.ink }}
    >
      <div className="ncard-meta" style={{ color: palette.muted }}>
        <span className="ncard-source">{card.source}</span>
        <span className="ncard-dot">·</span>
        <span>{card.time}</span>
        <span className="ncard-tag" style={{ background: palette.ink, color: palette.bg }}>{card.tag}</span>
      </div>
      <h3 className="ncard-title" style={{ color: palette.ink }}>{card.title}</h3>
      <p className="ncard-blurb" style={{ color: palette.muted }}>{card.blurb}</p>
      <div className="ncard-actions">
        <button className="ncard-link" onClick={() => onAction('read', card)} style={{ color: palette.ink }}>
          Read article <Icon name="external" size={12} />
        </button>
        <button className="ncard-link soft" onClick={() => onAction('more', card)} style={{ color: palette.muted }}>
          Explore more
        </button>
      </div>
    </article>
  )
}
