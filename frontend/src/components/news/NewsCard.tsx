'use client'

import type { NewsCard as NewsCardType, Palette } from '@/types'

interface Props {
  card: NewsCardType
  palette: Palette
  onAction: (kind: string, card: NewsCardType) => void
}

export default function NewsCard({ card, palette, onAction }: Props) {
  return (
    <button className="nitem" onClick={() => onAction('read', card)} style={{ color: palette.ink }}>
      {card.image_url && (
        <span className="nitem-img-wrap">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={card.image_url} alt="" className="nitem-img" loading="lazy" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
        </span>
      )}
      <span className="nitem-body">
        <span className="nitem-meta" style={{ color: palette.muted }}>
          {card.source} · {card.time}
        </span>
        <span className="nitem-title">{card.title}</span>
      </span>
    </button>
  )
}
