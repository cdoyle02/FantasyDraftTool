/// <reference lib="webworker" />
import { normalizeRecommendations, serializeRecommendationRequest, type RecommendationRequest } from '../api/client'

interface PyodideRuntime {
  loadPackage: (name: string) => Promise<void>
  runPythonAsync: (code: string) => Promise<{ toJs?: (options: unknown) => unknown } | unknown>
  globals: { set: (key: string, value: unknown) => void }
}

type LoadPyodide = (options: { indexURL: string }) => Promise<PyodideRuntime>

const PYODIDE_VERSION = '314.0.4'
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`
const WHEEL_URL = import.meta.env.VITE_DVS_WHEEL_URL ?? '/engine/dvs_engine-0.2.0-py3-none-any.whl'
let ready: Promise<PyodideRuntime> | undefined

async function getPython() {
  if (!ready) {
    const initialization = (async () => {
      const { loadPyodide } = await import(
        /* @vite-ignore */ `${INDEX_URL}pyodide.mjs`
      ) as { loadPyodide: LoadPyodide }
      const python = await loadPyodide({ indexURL: INDEX_URL })
      await python.loadPackage('micropip')
      python.globals.set('wheel_url', WHEEL_URL)
      await python.runPythonAsync('import micropip\nawait micropip.install(wheel_url)')
      return python
    })()
    ready = initialization
    void initialization.catch(() => {
      if (ready === initialization) ready = undefined
    })
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
