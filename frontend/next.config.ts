import type { NextConfig } from 'next'

// Static export — this app is a client-rendered SPA (no API routes, no
// server actions, no next/image), so it builds to plain HTML/CSS/JS in
// `out/` and needs no Node server. Required for hosting on Azure Storage
// static website (see infra/main.bicep + .github/workflows/deploy-frontend.yml).
const nextConfig: NextConfig = {
  output: 'export',
}

export default nextConfig
