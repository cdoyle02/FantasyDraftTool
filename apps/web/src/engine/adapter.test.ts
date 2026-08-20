import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { draftApi, type RecommendationRequest } from '../api/client'
import { seedPlayers } from '../data/seed'
import { defaultLeague, type Recommendation } from '../types'
import { getRecommendations } from './adapter'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    draftApi: { recommendations: vi.fn() }
  }
})

const recommendation: Recommendation = {
  playerId: seedPlayers[0].id,
  playerName: seedPlayers[0].name,
  position: seedPlayers[0].position,
  dvsScore: 42,
  tierLabel: 'BEST PICK',
  breakdown: {
    vorp: 30,
    marginalValue: 28,
    waitLoss: 6,
    tierUrgency: 4,
    survivalProbability: 0.3,
    needMultiplier: 1.1,
    opponentDemandFactor: 1,
    guardrailAdjustment: 0
  },
  explanation: 'Test recommendation'
}

const request: RecommendationRequest = {
  players: seedPlayers,
  picks: [],
  settings: defaultLeague,
  adjustments: []
}

type WorkerReply = {
  result?: { recommendations: Recommendation[] }
  error?: string
}

let workerReply: WorkerReply
let workerCreations = 0

class MockWorker {
  private readonly listeners = new Set<(event: MessageEvent) => void>()

  constructor() {
    workerCreations += 1
  }

  addEventListener(_type: string, listener: (event: MessageEvent) => void) {
    this.listeners.add(listener)
  }

  removeEventListener(_type: string, listener: (event: MessageEvent) => void) {
    this.listeners.delete(listener)
  }

  postMessage(message: { id: string }) {
    queueMicrotask(() => {
      const event = { data: { id: message.id, ...workerReply } } as MessageEvent
      this.listeners.forEach((listener) => listener(event))
    })
  }
}

const recommendationsMock = vi.mocked(draftApi.recommendations)

beforeEach(() => {
  Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
  vi.stubGlobal('Worker', MockWorker)
  workerReply = { result: { recommendations: [recommendation] } }
  workerCreations = 0
})

afterEach(() => {
  recommendationsMock.mockReset()
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('DVS engine adapter', () => {
  it('returns API recommendations without starting Pyodide', async () => {
    recommendationsMock.mockResolvedValue({ recommendations: [recommendation], count: 1 })

    await expect(getRecommendations(request)).resolves.toEqual({
      recommendations: [recommendation],
      mode: 'online-api'
    })
    expect(workerCreations).toBe(0)
  })

  it('recovers from an API failure with Pyodide recommendations', async () => {
    recommendationsMock.mockRejectedValue(new Error('API unavailable'))

    await expect(getRecommendations(request)).resolves.toEqual({
      recommendations: [recommendation],
      mode: 'offline-python'
    })
  })

  it('fails closed when both production engines are unavailable', async () => {
    vi.stubEnv('PROD', true)
    recommendationsMock.mockRejectedValue(new Error('API unavailable'))
    workerReply = { error: 'Pyodide unavailable' }

    const result = await getRecommendations(request)

    expect(result.recommendations).toEqual([])
    expect(result.mode).toBe('unavailable')
    expect(result.warning).toContain('Manual draft entry remains available')
  })
})
