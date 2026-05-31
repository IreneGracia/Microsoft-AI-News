'use client'

import NewsCard from '@/components/news/NewsCard'
import Icon from '@/components/ui/Icon'
import { CARD_ACTIONS, FOLLOWUPS } from '@/constants/data'
import type { NewsCard as NewsCardType, Palette } from '@/types'

interface Props {
  cards: NewsCardType[]
  palette: Palette
  onAction: (kind: string, card: NewsCardType) => void
  onActionChip: (a: { id: string; label: string; icon: string }) => void
  onFollowup: (f: string) => void
  followups?: string[]
}

export default function CardsBlock({ cards, palette, onAction, onActionChip, onFollowup, followups }: Props) {
  const suggestions = followups && followups.length > 0 ? followups : FOLLOWUPS
  return (
    <div className="cards-block">
      <div className="cards-grid">
        {cards.map((c) => <NewsCard key={c.id} card={c} palette={palette} onAction={onAction} />)}
      </div>
      <div className="action-row">
        {CARD_ACTIONS.map((a) => (
          <button key={a.id} className="action-chip" onClick={() => onActionChip(a)}
            style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.12)', background: 'rgba(255,253,247,0.6)' }}>
            <Icon name={a.icon as Parameters<typeof Icon>[0]['name']} />
            <span>{a.label}</span>
          </button>
        ))}
      </div>
      <div className="followups">
        <div className="followups-label" style={{ color: palette.muted }}>Or ask</div>
        {suggestions.map((f) => (
          <button key={f} className="followup" onClick={() => onFollowup(f)}
            style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.08)' }}>
            <span>{f}</span>
            <Icon name="arrow" size={13} />
          </button>
        ))}
      </div>
    </div>
  )
}
