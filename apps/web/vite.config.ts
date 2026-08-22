import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  worker: {
    format: 'es',
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Fantasy Draft Tool',
        short_name: 'Draft Tool',
        description: 'Local-first, explainable fantasy football draft assistant',
        theme_color: '#07120d',
        background_color: '#07120d',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }
        ]
      },
      workbox: {
        clientsClaim: true,
        skipWaiting: true,
        globPatterns: ['**/*.{js,mjs,wasm,zip,json,css,html,svg,woff2,whl}'],
        maximumFileSizeToCacheInBytes: 15 * 1024 * 1024,
      }
    })
  ],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/**']
  }
})
