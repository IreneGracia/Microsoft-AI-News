'use client'

import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import type { Palette } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  size?: number
}

export default function Wordmark({ palette, displayFont, newsFont, size = 26 }: Props) {
  return (
    <span className="wordmark" style={{ color: palette.ink }}>
      <span className="wm-mai" style={{ fontFamily: FONTS[displayFont], fontSize: size }}>
        MAI
      </span>
      <span
        className="wm-news"
        style={{ fontFamily: NEWS_FONTS[newsFont], fontSize: size * 0.5, color: palette.accent }}
      >
        news
      </span>
    </span>
  )
}
