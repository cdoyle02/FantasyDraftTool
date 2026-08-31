import { describe, expect, it } from 'vitest'
import { defaultLeague } from '../types'
import { developmentFallbackScore } from './fallback'
import { fallbackFixturePlayers } from './fallback.fixture'

describe('development fallback scorer', () => {
  it('ranks available players and exposes explainable components', () => {
    const recommendations = developmentFallbackScore(fallbackFixturePlayers, [], defaultLeague)
    expect(recommendations).toHaveLength(8)
    expect(recommendations[0].dvsScore).toBeGreaterThan(recommendations[1].dvsScore)
    expect(recommendations[0].breakdown).toEqual(expect.objectContaining({
      vorp: expect.any(Number),
      survivalProbability: expect.any(Number),
      needMultiplier: expect.any(Number)
    }))
  })

  it('suppresses kicker and defense before final rounds', () => {
    const result = developmentFallbackScore(fallbackFixturePlayers, [], defaultLeague)
    expect(result.map((recommendation) => recommendation.playerId)).not.toContain('seed-24')
  })
})
