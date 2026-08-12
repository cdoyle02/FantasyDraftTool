import { describe, expect, it } from 'vitest'
import { seedPlayers } from '../data/seed'
import { defaultLeague } from '../types'
import { developmentFallbackScore } from './fallback'

describe('development fallback scorer', () => {
  it('ranks available players and exposes explainable components', () => {
    const recommendations = developmentFallbackScore(seedPlayers, [], defaultLeague)
    expect(recommendations).toHaveLength(8)
    expect(recommendations[0].dvsScore).toBeGreaterThan(recommendations[1].dvsScore)
    expect(recommendations[0].breakdown).toEqual(expect.objectContaining({
      vorp: expect.any(Number),
      survivalProbability: expect.any(Number),
      needMultiplier: expect.any(Number)
    }))
  })

  it('suppresses kicker and defense before final rounds', () => {
    const result = developmentFallbackScore(seedPlayers, [], defaultLeague)
    expect(result.map((recommendation) => recommendation.playerId)).not.toContain('seed-24')
  })
})
