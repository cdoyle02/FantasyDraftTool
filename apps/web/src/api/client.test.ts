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
      keepers: [],
      settings: defaultLeague,
      adjustments: [adjustment]
    })

    expect(payload.players[0]).not.toHaveProperty('pointsDelta')
    expect(payload.adjustments).toEqual([adjustment])
    expect(payload.settings.userTeamId).toBe(String(defaultLeague.userTeam))
    expect(payload.settings.formulaVersion).toBe(4)
    expect(payload.draftState.reservedRosters).toEqual({})
  })

  it('serializes keeper assignments as reserved rosters without pick history', () => {
    const payload = serializeRecommendationRequest({
      players: [player],
      picks: [],
      keepers: [{
        id: 'keeper-1',
        teamId: 6,
        playerId: player.id,
        playerName: player.name,
        position: player.position,
        roundCost: 1,
        timestamp: 1
      }],
      settings: defaultLeague,
      adjustments: []
    })

    expect(payload.draftState.pickHistory).toEqual([])
    expect(payload.draftState.reservedRosters).toEqual({ '6': [player.id] })
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
        guardrail_adjustment: 0,
        adjusted_survival_probability: 0.25,
        expected_next_pick_value: 18,
        two_pick_path_value: 46,
        tier_opportunity_cost: 4,
        shape_adjustment: 2
      },
      reasons: ['30.0 points above replacement']
    }])

    expect(result.playerId).toBe(player.id)
    expect(result.breakdown.survivalProbability).toBe(0.3)
    expect(result.breakdown.marginalValue).toBe(28)
    expect(result.breakdown.waitLoss).toBe(6)
    expect(result.breakdown.adjustedSurvivalProbability).toBe(0.25)
    expect(result.breakdown.expectedNextPickValue).toBe(18)
    expect(result.breakdown.twoPickPathValue).toBe(46)
    expect(result.explanation).toContain('above replacement')
  })
})
