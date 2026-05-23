import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MAI — Tech news, made yours.',
  description: 'AI-powered tech news personalized to your role, region, and depth.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700&family=DM+Serif+Display:ital@0;1&family=Inter+Tight:wght@300;400;450;500;600&family=Bricolage+Grotesque:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600&family=Major+Mono+Display&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  )
}
