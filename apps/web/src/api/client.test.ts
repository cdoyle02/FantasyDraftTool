import { describe, expect, it } from 'vitest'
import { defaultLeague, type Player, type UserAdjustment } from '../types'
import { normalizeRecommendationResponse, normalizeRecommendations, serializeRecommendationRequest } from './client'

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
        shape_adjustment: 2,
        optionality_value: 3.5,
        late_round_upside: 2.0,
        handcuff_bonus: 3.5,
        ir_stash_value: 1.5,
        late_phase_weight: 0.75,
        starter_completion: 0.86,
        replacement_level: 150,
        decision_score: 42
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
    expect(result.breakdown.optionalityValue).toBe(3.5)
    expect(result.breakdown.lateRoundUpside).toBe(2)
    expect(result.breakdown.handcuffBonus).toBe(3.5)
    expect(result.breakdown.irStashValue).toBe(1.5)
    expect(result.breakdown.latePhaseWeight).toBe(0.75)
    expect(result.breakdown.shapeAdjustment).toBe(2)
    expect(result.breakdown.decisionScore).toBe(42)
    expect(result.breakdown.starterCompletion).toBe(0.86)
    expect(result.breakdown.replacementLevel).toBe(150)
    expect(result.explanation).toContain('above replacement')
  })

  it('preserves the effective engine formula and simulation configuration', () => {
    const response = normalizeRecommendationResponse({
      recommendations: [],
      count: 0,
      configuration: {
        formulaVersion: 4,
        oneTurnSims: 48,
        simulationSeed: 2026,
        formulaParams: {
          formula_version: 4,
          one_turn_sims: 48,
          sim_seed: 2026,
          wait_loss_weight_v4: 0.35
        }
      }
    })

    expect(response.configuration).toEqual({
      formulaVersion: 4,
      oneTurnSims: 48,
      simulationSeed: 2026,
      formulaParams: {
        formula_version: 4,
        one_turn_sims: 48,
        sim_seed: 2026,
        wait_loss_weight_v4: 0.35
      }
    })
  })

  it('normalizes optional V5 breakdown fields', () => {
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
        negative_vorp_adjustment: -1.2,
        adjusted_handcuff_bonus: 4.5,
        bench_balance_adjustment: 0.5,
        reliability_adjustment: 0.25,
        v5_policy_strength: 1.0,
        decision_score: 42
      },
      reasons: ['significantly below shallow-league replacement level']
    }])

    expect(result.breakdown.negativeVorpAdjustment).toBe(-1.2)
    expect(result.breakdown.adjustedHandcuffBonus).toBe(4.5)
    expect(result.breakdown.benchBalanceAdjustment).toBe(0.5)
    expect(result.breakdown.reliabilityAdjustment).toBe(0.25)
    expect(result.breakdown.v5PolicyStrength).toBe(1.0)
  })
})
