import type { Palette } from '@/types'

export const PALETTES: Record<string, Palette> = {
  moss: {
    name: 'Moss & Ember',
    bg: '#f4ede1', ink: '#1f1d18', muted: '#6b6557',
    blobs: ['#5a6b3d', '#c66a3a', '#d9a05b', '#3a4a3c'],
    accent: '#5a6b3d',
    bubbleAi: 'rgba(255,253,247,0.72)',
    bubbleUser: '#1f1d18', bubbleUserInk: '#f4ede1',
    cardBg: 'rgba(255,253,247,0.78)',
  },
  rose: {
    name: 'Rose Dust',
    bg: '#f1e3da', ink: '#2a1f1c', muted: '#7a6660',
    blobs: ['#c98c8c', '#d9a89a', '#a86e6e', '#e9b48a'],
    accent: '#a86e6e',
    bubbleAi: 'rgba(255,250,245,0.74)',
    bubbleUser: '#2a1f1c', bubbleUserInk: '#f1e3da',
    cardBg: 'rgba(255,250,245,0.82)',
  },
  ochre: {
    name: 'Ochre Field',
    bg: '#f3e7c6', ink: '#211c11', muted: '#6e6347',
    blobs: ['#caa14a', '#8a6b2e', '#d97a3a', '#5a5a2c'],
    accent: '#8a6b2e',
    bubbleAi: 'rgba(255,251,238,0.76)',
    bubbleUser: '#211c11', bubbleUserInk: '#f3e7c6',
    cardBg: 'rgba(255,251,238,0.84)',
  },
  teal: {
    name: 'Teal Dusk',
    bg: '#e6e7e1', ink: '#15201f', muted: '#5a6562',
    blobs: ['#3d6b66', '#2a4a4a', '#a89a6a', '#c4836a'],
    accent: '#3d6b66',
    bubbleAi: 'rgba(252,253,250,0.74)',
    bubbleUser: '#15201f', bubbleUserInk: '#e6e7e1',
    cardBg: 'rgba(252,253,250,0.82)',
  },
}
