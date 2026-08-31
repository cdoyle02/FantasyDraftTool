import { cp, mkdir, stat } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { PYODIDE_RUNTIME_FILES } from './pyodide-files.mjs'

const root = new URL('../', import.meta.url)
const source = new URL('node_modules/pyodide/', root)
const destination = new URL('dist/pyodide/', root)

await mkdir(destination, { recursive: true })
await Promise.all(PYODIDE_RUNTIME_FILES.map(async (file) => {
  const from = new URL(file, source)
  const to = new URL(file, destination)
  try {
    await stat(from)
  } catch {
    throw new Error(`Missing Pyodide runtime file: ${fileURLToPath(from)}. Run pnpm install in apps/web first.`)
  }
  await cp(from, to, { force: true })
}))
console.log(`Copied ${PYODIDE_RUNTIME_FILES.length} Pyodide runtime files to ${fileURLToPath(destination)}`)
