import { draftApi, type RecommendationRequest } from '../api/client'
import type { Recommendation } from '../types'
import { developmentFallbackScore } from './fallback'

export type EngineMode = 'online-api' | 'offline-python' | 'development-fallback'

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

async function pythonRecommendations(request: RecommendationRequest): Promise<Recommendation[]> {
  const engineWorker = getWorker()
  const id = crypto.randomUUID()
  return new Promise((resolve, reject) => {
    let timeout = 0
    const listener = (event: MessageEvent<{ id: string; result?: { recommendations: Recommendation[] }; error?: string }>) => {
      if (event.data.id !== id) return
      engineWorker.removeEventListener('message', listener)
      window.clearTimeout(timeout)
      if (event.data.error) reject(new Error(event.data.error))
      else resolve(event.data.result?.recommendations ?? [])
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
  warning?: string
}> {
  if (navigator.onLine) {
    try {
      const response = await draftApi.recommendations(request)
      return { recommendations: response.recommendations, mode: 'online-api' }
    } catch {
      // API is optional for the local-first client.
    }
  }
  try {
    return { recommendations: await pythonRecommendations(request), mode: 'offline-python' }
  } catch (error) {
    return {
      recommendations: developmentFallbackScore(request.players, request.picks, request.settings, request.adjustments, request.keepers),
      mode: 'development-fallback',
      warning: `Non-production TypeScript scorer active: ${error instanceof Error ? error.message : 'Python engine unavailable'}`
    }
  }
}
