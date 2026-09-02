import { draftApi, type RecommendationRequest, type RecommendationResponse } from '../api/client'
import type { EngineMode, FormulaConfigurationSnapshot, Recommendation } from '../types'
import { developmentFallbackScore } from './fallback'

export type { EngineMode } from '../types'

let worker: Worker | undefined

export function createOfflineWorker() {
  return new Worker(new URL('../workers/dvs.worker.ts', import.meta.url), { type: 'module' })
}

function getWorker() {
  worker ??= createOfflineWorker()
  return worker
}

export async function prepareOfflineEngine(): Promise<void> {
  if (import.meta.env.PROD && 'serviceWorker' in navigator) {
    await navigator.serviceWorker.ready
  }
  const engineWorker = getWorker()
  const id = crypto.randomUUID()
  return new Promise((resolve, reject) => {
    let timeout = 0
    const listener = (event: MessageEvent<{ id: string; ready?: boolean; error?: string }>) => {
      if (event.data.id !== id) return
      engineWorker.removeEventListener('message', listener)
      window.clearTimeout(timeout)
      if (event.data.error) reject(new Error(event.data.error))
      else resolve()
    }
    timeout = window.setTimeout(() => {
      engineWorker.removeEventListener('message', listener)
      reject(new Error('Offline engine preparation timed out'))
    }, 60_000)
    engineWorker.addEventListener('message', listener)
    engineWorker.postMessage({ id, type: 'prepare' })
  })
}

async function pythonRecommendations(request: RecommendationRequest): Promise<RecommendationResponse> {
  const engineWorker = getWorker()
  const id = crypto.randomUUID()
  return new Promise((resolve, reject) => {
    let timeout = 0
    const listener = (event: MessageEvent<{ id: string; result?: RecommendationResponse; error?: string }>) => {
      if (event.data.id !== id) return
      engineWorker.removeEventListener('message', listener)
      window.clearTimeout(timeout)
      if (event.data.error) reject(new Error(event.data.error))
      else if (event.data.result) resolve(event.data.result)
      else reject(new Error('Offline engine returned no recommendation result'))
    }
    timeout = window.setTimeout(() => {
      engineWorker.removeEventListener('message', listener)
      reject(new Error('Offline engine timed out'))
    }, 20_000)
    engineWorker.addEventListener('message', listener)
    engineWorker.postMessage({ id, type: 'recommend', request })
  })
}

export async function getRecommendations(request: RecommendationRequest): Promise<{
  recommendations: Recommendation[]
  mode: EngineMode
  configuration: FormulaConfigurationSnapshot
  warning?: string
}> {
  if (navigator.onLine) {
    try {
      const response = await draftApi.recommendations(request)
      return {
        recommendations: response.recommendations,
        configuration: response.configuration,
        mode: 'online-api'
      }
    } catch {
      // API is optional for the local-first client.
    }
  }
  try {
    const response = await pythonRecommendations(request)
    return {
      recommendations: response.recommendations,
      configuration: response.configuration,
      mode: 'offline-python'
    }
  } catch (error) {
    return {
      recommendations: developmentFallbackScore(request.players, request.picks, request.settings, request.adjustments, request.keepers),
      configuration: {
        formulaVersion: request.settings.formulaVersion ?? null,
        oneTurnSims: null,
        simulationSeed: null,
        formulaParams: null
      },
      mode: 'development-fallback',
      warning: `Non-production TypeScript scorer active: ${error instanceof Error ? error.message : 'Python engine unavailable'}`
    }
  }
}
