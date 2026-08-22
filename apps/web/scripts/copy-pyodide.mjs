import { cp, mkdir, rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const root = new URL('../', import.meta.url)
const source = new URL('node_modules/pyodide/', root)
const destination = new URL('public/pyodide/', root)
const files = ['pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']

await rm(destination, { recursive: true, force: true })
await mkdir(destination, { recursive: true })
await Promise.all(files.map((file) => cp(new URL(file, source), new URL(file, destination))))
console.log(`Copied ${files.length} Pyodide runtime files to ${fileURLToPath(destination)}`)
