import { createReadStream, existsSync } from 'node:fs'
import { cp, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

const appRoot = fileURLToPath(new URL('.', import.meta.url))
const pyodideDir = path.join(appRoot, 'node_modules/pyodide')
const PYODIDE_RUNTIME_FILES = [
  'pyodide.asm.mjs',
  'pyodide.asm.wasm',
  'python_stdlib.zip',
  'pyodide-lock.json'
]
const MIME_TYPES: Record<string, string> = {
  '.mjs': 'application/javascript',
  '.wasm': 'application/wasm',
  '.zip': 'application/zip',
  '.json': 'application/json'
}

function pyodideRuntimePlugin(): Plugin {
  return {
    name: 'pyodide-runtime',
    enforce: 'pre',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split('?')[0] ?? ''
        if (!url.startsWith('/pyodide/')) {
          next()
          return
        }
        const rel = decodeURIComponent(url.slice('/pyodide/'.length))
        if (!rel || rel.includes('..')) {
          next()
          return
        }
        const filePath = path.resolve(pyodideDir, rel)
        const relative = path.relative(pyodideDir, filePath)
        if (relative.startsWith('..') || path.isAbsolute(relative) || !existsSync(filePath)) {
          next()
          return
        }
        res.setHeader('Content-Type', MIME_TYPES[path.extname(filePath)] ?? 'application/octet-stream')
        createReadStream(filePath).pipe(res)
      })
    },
    async closeBundle() {
      const distDir = path.join(appRoot, 'dist')
      const publicDir = path.join(appRoot, 'public')
      await mkdir(distDir, { recursive: true })
      for (const entry of ['icon.svg', '_redirects']) {
        const source = path.join(publicDir, entry)
        if (existsSync(source)) {
          await cp(source, path.join(distDir, entry))
        }
      }
      const engineDir = path.join(publicDir, 'engine')
      if (existsSync(engineDir)) {
        await cp(engineDir, path.join(distDir, 'engine'), { recursive: true })
      }
      const outDir = path.join(distDir, 'pyodide')
      await mkdir(outDir, { recursive: true })
      await Promise.all(
        PYODIDE_RUNTIME_FILES.map((file) => cp(path.join(pyodideDir, file), path.join(outDir, file)))
      )
    }
  }
}

export default defineConfig({
  worker: {
    format: 'es',
  },
  build: {
    copyPublicDir: false
  },
  plugins: [
    pyodideRuntimePlugin(),
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
