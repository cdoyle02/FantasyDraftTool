/// <reference lib="webworker" />
import { loadPyodide } from 'pyodide'
import { normalizeRecommendationResponse, serializeRecommendationRequest, type RecommendationRequest } from '../api/client'

const PYODIDE_INDEX_URL = '/pyodide/'
const WHEEL_URL = import.meta.env.VITE_DVS_WHEEL_URL ?? '/engine/dvs_engine-0.1.0-py3-none-any.whl'
let ready: Promise<Awaited<ReturnType<typeof loadPyodide>>> | undefined

async function getPython() {
  if (!ready) {
    ready = (async () => {
      const python = await loadPyodide({ indexURL: PYODIDE_INDEX_URL })
      python.globals.set('wheel_url', WHEEL_URL)
      await python.runPythonAsync(
        'from pyodide.http import pyfetch\n'
        + 'response = await pyfetch(wheel_url)\n'
        + 'await response.unpack_archive()'
      )
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
      result: normalizeRecommendationResponse(JSON.parse(raw))
    })
  } catch (error) {
    self.postMessage({ id: event.data.id, error: error instanceof Error ? error.message : String(error) })
  }
}

export {}
