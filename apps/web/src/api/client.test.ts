import { describe, expect, it } from 'vitest'
import { defaultLeague, type Player, type UserAdjustment } from '../types'
import { normalizeRecommendations, serializeRecommendationRequest } from './client'

const player: Player = {
  id: 'player-1',
  name: 'Test Runner',
  position: 'RB',
  team: 'TST',
  projectedPoints: 250,
  adp: 12,
  tier: 1
}

describe('DVS API contract adapter', () => {
  it('keeps baseline players and user opinions in separate payload layers', () => {
    const adjustment: UserAdjustment = {
      playerId: player.id,
      pointsDelta: 7,
      tierOverride: 2,
      tag: 'myGuy'
    }
    const payload = serializeRecommendationRequest({
      players: [player],
      picks: [],
      settings: defaultLeague,
      adjustments: [adjustment]
    })

    expect(payload.players[0]).not.toHaveProperty('pointsDelta')
    expect(payload.adjustments).toEqual([adjustment])
    expect(payload.settings.userTeamId).toBe(String(defaultLeague.userTeam))
  })

  it('normalizes Python snake-case results for the React UI', () => {
    const [result] = normalizeRecommendations([{
      player_id: player.id,
      player_name: player.name,
      position: player.position,
      dvs_score: 42,
      tier_label: 'BEST PICK',
      breakdown: {
        vorp: 30,
        marginal_value: 28,
        wait_loss: 6,
        tier_urgency: 4,
        survival_probability: 0.3,
        need_multiplier: 1.1,
        opponent_demand_factor: 1,
        guardrail_adjustment: 0
      },
      reasons: ['30.0 points above replacement']
    }])

    expect(result.playerId).toBe(player.id)
    expect(result.breakdown.survivalProbability).toBe(0.3)
    expect(result.breakdown.marginalValue).toBe(28)
    expect(result.breakdown.waitLoss).toBe(6)
    expect(result.explanation).toContain('above replacement')
  })
})
