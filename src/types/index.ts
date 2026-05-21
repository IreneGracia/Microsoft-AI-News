export interface Palette {
  name: string
  bg: string
  ink: string
  muted: string
  blobs: [string, string, string, string]
  accent: string
  bubbleAi: string
  bubbleUser: string
  bubbleUserInk: string
  cardBg: string
}

export interface User {
  name: string
  email: string
  department: string
  region: string
  signedInAt: number
  sso?: boolean
  rememberMe?: boolean
}

export interface Thread {
  id: string
  title: string
  time: string
}

export interface NewsCard {
  id: string
  source: string
  time: string
  kind: string
  title: string
  blurb: string
  tone: 'lead' | 'calm'
  tag: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'ai'
  content?: string
  thinking?: boolean
  cards?: NewsCard[]
}

export interface Prefs {
  role?: string
  region?: string
  topics?: string[]
  depth?: string
  delivery?: string[]
  keywords?: string
  tone?: string
  energy?: number
}

export interface Tweaks {
  palette: string
  displayFont: string
  grain: number
  blur: number
  showSuggestions: boolean
  compactMessages: boolean
  tagline: string
  newsFont: string
  preloadDemo: boolean
}

export interface MockAccount {
  name: string
  email: string
  department: string
  region: string
  initial: string
  color: string
}
