export const PREF_ROLES = [
  { id: 'engineer', label: 'For engineers',          note: 'Technical depth — model details, code, infra',     defaultDepth: 'deep'  },
  { id: 'business', label: 'For business & sales',   note: 'Markets, deals, what to tell customers',           defaultDepth: 'brief' },
  { id: 'legal',    label: 'For legal & compliance', note: 'Regulation, antitrust, privacy law',               defaultDepth: 'brief' },
  { id: 'exec',     label: 'For executives',         note: 'Strategic, high-level signals',                    defaultDepth: 'brief' },
  { id: 'research', label: 'For researchers',        note: 'Papers, benchmarks, deep technical reads',         defaultDepth: 'deep'  },
]

export const TOPIC_GROUPS = [
  {
    id: 'topic', label: 'Technology', note: 'Core tech beats',
    items: [
      { id: 'ai_ml',     label: 'AI & ML' },
      { id: 'cyber',     label: 'Cybersecurity' },
      { id: 'cloud',     label: 'Cloud & Infrastructure' },
      { id: 'softdev',   label: 'Software Development' },
      { id: 'hardware',  label: 'Hardware & Chips' },
      { id: 'privacy',   label: 'Data & Privacy' },
      { id: 'quantum',   label: 'Quantum Computing' },
      { id: 'robotics',  label: 'Robotics & Automation' },
      { id: 'fintech',   label: 'Fintech & Payments' },
      { id: 'health',    label: 'Health & Biotech' },
      { id: 'cleantech', label: 'Clean Tech & Sustainability' },
      { id: 'space',     label: 'Space & Satellites' },
      { id: 'xr',        label: 'Metaverse & XR' },
    ],
  },
  {
    id: 'business', label: 'Business', note: 'Money, deals, who\'s hiring',
    items: [
      { id: 'ma',       label: 'M&A & Funding' },
      { id: 'ipo',      label: 'IPO & Markets' },
      { id: 'bigtech',  label: 'Big Tech (FAANG+Microsoft)' },
      { id: 'startups', label: 'Startups & Venture' },
      { id: 'layoffs',  label: 'Layoffs & Hiring' },
      { id: 'earnings', label: 'Earnings & Revenue' },
    ],
  },
  {
    id: 'regulation', label: 'Regulation & Policy', note: 'Rules of the game',
    items: [
      { id: 'ai_reg',    label: 'AI Regulation' },
      { id: 'gdpr',      label: 'Data Protection (GDPR, DPDP, LGPD)' },
      { id: 'antitrust', label: 'Antitrust & Competition' },
      { id: 'exports',   label: 'Export Controls & Sanctions' },
      { id: 'digiinfra', label: 'Digital Infrastructure Policy' },
      { id: 'cyberpol',  label: 'Cybersecurity Policy' },
      { id: 'platform',  label: 'Platform Regulation' },
    ],
  },
]

export const PREF_DEPTHS = [
  { id: 'deep',  label: 'Deep dive', note: 'IC level — long-form, technical, with full context' },
  { id: 'brief', label: 'Brief',     note: 'Exec level — short, decision-focused, no jargon' },
]

export const PREF_DELIVERY = [
  { id: 'daily',    label: 'Daily brief',          note: 'Every morning, ranked and deduplicated' },
  { id: 'weekly',   label: 'Weekly digest',        note: 'One Sunday long-read of what mattered' },
  { id: 'breaking', label: 'Breaking-news alerts', note: 'Only when your keywords show up' },
]

export const PREF_TONES = [
  { id: 'calm',      label: 'Calm & editorial' },
  { id: 'plain',     label: 'Plain & direct' },
  { id: 'technical', label: 'Technical' },
]
