'use client'

type IconName = 'doc' | 'compare' | 'compass' | 'bookmark' | 'arrow' | 'external' | 'sparkle'

interface Props {
  name: IconName
  size?: number
}

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const ICONS: Record<IconName, React.ReactNode> = {
  doc:      <g {...stroke}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 13h6M9 17h6M9 9h2" /></g>,
  compare:  <g {...stroke}><path d="M3 7h7M3 7l3-3M3 7l3 3" /><path d="M21 17h-7M21 17l-3-3M21 17l-3 3" /></g>,
  compass:  <g {...stroke}><circle cx="12" cy="12" r="9" /><path d="m15 9-4 2-2 4 4-2 2-4z" /></g>,
  bookmark: <g {...stroke}><path d="M6 4h12v17l-6-4-6 4z" /></g>,
  arrow:    <g {...stroke}><path d="M5 12h14M13 6l6 6-6 6" /></g>,
  external: <g {...stroke}><path d="M14 5h5v5" /><path d="M19 5l-9 9" /><path d="M19 14v5H5V5h5" /></g>,
  sparkle:  <g {...stroke}><path d="M12 4v6M12 14v6M4 12h6M14 12h6" /></g>,
}

export default function Icon({ name, size = 14 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      {ICONS[name] ?? null}
    </svg>
  )
}
