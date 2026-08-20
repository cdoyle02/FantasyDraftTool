/// <reference lib="webworker" />
import { normalizeRecommendations, serializeRecommendationRequest, type RecommendationRequest } from '../api/client'

declare const self: DedicatedWorkerGlobalScope & {
  loadPyodide?: (options: { indexURL: string }) => Promise<{
    loadPackage: (name: string) => Promise<void>
    runPythonAsync: (code: string) => Promise<{ toJs?: (options: unknown) => unknown } | unknown>
    globals: { set: (key: string, value: unknown) => void }
  }>
}

const PYODIDE_VERSION = '314.0.4'
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`
const WHEEL_URL = import.meta.env.VITE_DVS_WHEEL_URL ?? '/engine/dvs_engine-0.1.0-py3-none-any.whl'
let ready: Promise<Awaited<ReturnType<NonNullable<typeof self.loadPyodide>>>> | undefined

async function getPython() {
  if (!ready) {
    ready = (async () => {
      importScripts(`${INDEX_URL}pyodide.js`)
      if (!self.loadPyodide) throw new Error('Pyodide runtime did not load')
      const python = await self.loadPyodide({ indexURL: INDEX_URL })
      await python.loadPackage('micropip')
      python.globals.set('wheel_url', WHEEL_URL)
      await python.runPythonAsync('import micropip\nawait micropip.install(wheel_url)')
      return python
    })()
  }
  return ready
}

self.onmessage = async (
  event: MessageEvent<
    { id: string; type: 'prepare' } |
    { id: string; type: 'recommend'; request: RecommendationRequest }
  >
) => {
  try {
    const python = await getPython()
    if (event.data.type === 'prepare') {
      self.postMessage({ id: event.data.id, ready: true })
      return
    }
    python.globals.set('payload_json', JSON.stringify(serializeRecommendationRequest(event.data.request)))
    const result = await python.runPythonAsync(
      'from dvs_engine import recommendation_json\nrecommendation_json(payload_json)'
    )
    const raw = typeof result === 'string' ? result : String(result)
    self.postMessage({
      id: event.data.id,
      result: { recommendations: normalizeRecommendations(JSON.parse(raw)) }
    })
  } catch (error) {
    self.postMessage({ id: event.data.id, error: error instanceof Error ? error.message : String(error) })
  }
}

export {}
