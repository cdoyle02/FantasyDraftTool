import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { draftApi, type RecommendationRequest } from '../api/client'
import { seedPlayers } from '../data/seed'
import { defaultLeague, type Recommendation } from '../types'
import { developmentFallbackScore } from './fallback'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    draftApi: {
      recommendations: vi.fn()
    }
  }
})

vi.mock('./fallback', () => ({
  developmentFallbackScore: vi.fn(() => [])
}))

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
    needMultiplier: 1,
    opponentDemandFactor: 1,
    guardrailAdjustment: 0
  },
  reasons: ['Best available value'],
  explanation: 'Best available value'
}

const request: RecommendationRequest = {
  players: seedPlayers,
  picks: [],
  settings: defaultLeague,
  adjustments: []
}

let workerReply: { result?: { recommendations: Recommendation[] }; error?: string }
const workerConstructor = vi.fn()

class FakeWorker {
  private listener?: (event: MessageEvent) => void

  constructor() {
    workerConstructor()
  }

  addEventListener(_type: string, listener: EventListenerOrEventListenerObject) {
    this.listener = listener as (event: MessageEvent) => void
  }

  removeEventListener() {
    this.listener = undefined
  }

  postMessage(message: { id: string }) {
    queueMicrotask(() => {
      this.listener?.(new MessageEvent('message', { data: { id: message.id, ...workerReply } }))
    })
  }
}

describe('recommendation engine adapter', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('Worker', FakeWorker)
    vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(true)
    vi.mocked(draftApi.recommendations).mockReset()
    vi.mocked(developmentFallbackScore).mockClear()
    workerConstructor.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('returns API recommendations without starting the offline worker', async () => {
    vi.mocked(draftApi.recommendations).mockResolvedValue({
      recommendations: [recommendation],
      count: 1
    })
    const { getRecommendations } = await import('./adapter')

    await expect(getRecommendations(request)).resolves.toEqual({
      recommendations: [recommendation],
      mode: 'online-api'
    })
    expect(workerConstructor).not.toHaveBeenCalled()
  })

  it('recovers from an API failure with offline Python recommendations', async () => {
    vi.mocked(draftApi.recommendations).mockRejectedValue(new Error('API unavailable'))
    workerReply = { result: { recommendations: [recommendation] } }
    const { getRecommendations } = await import('./adapter')

    await expect(getRecommendations(request)).resolves.toEqual({
      recommendations: [recommendation],
      mode: 'offline-python'
    })
  })

  it('fails closed when both production engines are unavailable', async () => {
    vi.stubEnv('PROD', true)
    vi.mocked(draftApi.recommendations).mockRejectedValue(new Error('API unavailable'))
    workerReply = { error: 'Wheel unavailable' }
    const { getRecommendations } = await import('./adapter')

    const result = await getRecommendations(request)

    expect(result).toEqual({
      recommendations: [],
      mode: 'unavailable',
      warning: expect.stringContaining('manual draft entry remains available')
    })
    expect(developmentFallbackScore).not.toHaveBeenCalled()
  })
})
