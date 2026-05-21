import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        'inter-tight': ["'Inter Tight'", 'system-ui', 'sans-serif'],
        'instrument': ["'Instrument Serif'", "'Cormorant Garamond'", 'Georgia', 'serif'],
        'fraunces': ["'Fraunces'", 'Georgia', 'serif'],
        'dm-serif': ["'DM Serif Display'", 'Georgia', 'serif'],
        'bricolage': ["'Bricolage Grotesque'", 'sans-serif'],
        'space-grotesk': ["'Space Grotesk'", 'sans-serif'],
        'major-mono': ["'Major Mono Display'", 'monospace'],
      },
    },
  },
  plugins: [],
}

export default config
