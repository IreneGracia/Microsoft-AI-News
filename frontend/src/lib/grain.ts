export function grainSvg(opacity: number): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(`
<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>
  <filter id='n'>
    <feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>
    <feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 ${opacity} 0'/>
  </filter>
  <rect width='100%' height='100%' filter='url(#n)'/>
</svg>`)}`
}
