'use client'

import { grainSvg } from '@/lib/grain'
import type { Palette } from '@/types'

interface Props {
  palette: Palette
  blur: number
  grain: number
}

export default function Backdrop({ palette, blur, grain }: Props) {
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
    </div>
  )
}
