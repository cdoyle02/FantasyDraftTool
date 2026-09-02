import { describe, expect, it } from 'vitest'
import { createDraftEvaluationRecord } from '../store/draftStore'
import { defaultLeague, type DraftPick, type Player, type Recommendation } from '../types'
import { buildDraftEvaluationExport } from './export'

const players: Player[] = Array.from({ length: 11 }, (_, index) => ({
  id: `player-${index + 1}`,
  name: `Player ${index + 1}`,
  position: index % 2 ? 'WR' : 'RB',
  team: 'TST',
  projectedPoints: 250 - index,
  adp: index + 1,
  tier: Math.floor(index / 4) + 1
}))

function recommendation(player: Player, index: number): Recommendation {
  const decisionScore = 80 - index
  return {
    playerId: player.id,
    playerName: player.name,
    position: player.position,
    dvsScore: decisionScore,
    tierLabel: 'BEST PICK',
    breakdown: {
      vorp: 30,
      marginalValue: 28,
      waitLoss: 6,
      tierUrgency: 4,
      tierOpportunityCost: 4,
      survivalProbability: 0.3,
      adjustedSurvivalProbability: 0.25,
      needMultiplier: 1.1,
      opponentDemandFactor: 1,
      guardrailAdjustment: 0,
      expectedNextPickValue: 18,
      shapeAdjustment: 2,
      decisionScore,
      lateRoundUpside: 2,
      handcuffBonus: 3.5,
      irStashValue: 1.5,
      latePhaseWeight: 0.75,
      replacementLevel: 150,
      projectedPoints: player.projectedPoints
    },
    reasons: ['Tier cliff', 'Roster need'],
    explanation: 'Tier cliff · Roster need'
  }
}

describe('draft evaluation export', () => {
  it('builds a reproducible schema-v2 bundle with ranked recommendations and the human pick', () => {
    const recommendations = players.map(recommendation)
    const actual = players[10]
    const pick: DraftPick = {
      id: 'pick-1',
      pickNumber: 1,
      teamId: 1,
      playerId: actual.id,
      playerName: actual.name,
      position: actual.position,
      timestamp: 100
    }
    const record = createDraftEvaluationRecord({
      players,
      adjustments: {},
      picks: [],
      keepers: [],
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 },
      recommendations,
      recommendationContext: {
        formulaVersion: 4,
        oneTurnSims: 48,
        simulationSeed: 2026,
        formulaParams: {
          formula_version: 4,
          one_turn_sims: 48,
          sim_seed: 2026,
          wait_loss_weight_v4: 0.35
        },
        engineMode: 'offline-python',
        generatedAt: 90,
        generatedForPickIds: [],
        generatedForPickCount: 0
      },
      engineMode: 'offline-python'
    }, pick, actual)
    const bundle = buildDraftEvaluationExport({
      settings: defaultLeague,
      players,
      adjustments: {},
      picks: [pick],
      keepers: [],
      evaluationRecords: [record]
    }, '2026-09-02T15:00:00.000Z')

    expect(bundle.schemaVersion).toBe(2)
    expect(bundle.exportedAt).toBe('2026-09-02T15:00:00.000Z')
    expect(bundle.finalState.picks).toEqual([pick])
    expect(bundle.evaluationRecords[0].boardState.picks).toEqual([])
    expect(bundle.evaluationRecords[0].availablePlayerPool).toHaveLength(11)
    expect(bundle.evaluationRecords[0].topRecommendations.map((item) => item.rank)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    ])

    const top = bundle.evaluationRecords[0].topRecommendations[0]
    expect(top.player).toMatchObject({ adp: 1, tier: 1, projectedPoints: 250 })
    expect(top.breakdown).toMatchObject({
      decisionScore: 80,
      marginalValue: 28,
      waitLoss: 6,
      tierOpportunityCost: 4,
      expectedNextPickValue: 18,
      shapeAdjustment: 2,
      lateRoundUpside: 2,
      handcuffBonus: 3.5,
      irStashValue: 1.5,
      latePhaseWeight: 0.75,
      adjustedSurvivalProbability: 0.25,
      replacementLevel: 150
    })
    expect(top.reasonStrings).toEqual(['Tier cliff', 'Roster need'])
    expect(bundle.evaluationRecords[0]).toMatchObject({
      actualSelection: { id: 'player-11' },
      actualSelectionRecommendationRank: null,
      actualSelectionDecisionScore: 70,
      recommendationGeneration: {
        formulaVersion: 4,
        oneTurnSims: 48,
        simulationSeed: 2026,
        engineMode: 'offline-python'
      }
    })
    expect(bundle.evaluationRecords[0].actualSelectionScoreBreakdown?.decisionScore).toBe(70)
  })
})
