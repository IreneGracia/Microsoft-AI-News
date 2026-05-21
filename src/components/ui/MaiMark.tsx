'use client'

import { grainSvg } from '@/lib/grain'
import type { Palette } from '@/types'

interface Props {
  palette: Palette
  size?: number
}

export default function MaiMark({ palette, size = 36 }: Props) {
  return (
    <div className="mai-mark" style={{ width: size, height: size }}>
      <div
        className="mm-grain"
        style={{
          background: `radial-gradient(circle at 30% 30%, ${palette.blobs[1]}, ${palette.blobs[0]} 55%, ${palette.blobs[3]} 100%)`,
        }}
      />
      <div
        className="mm-grain-overlay"
        style={{ backgroundImage: `url("${grainSvg(0.35)}")` }}
      />
    </div>
  )
}
