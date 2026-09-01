import type { DraftPick, KeeperAssignment, LeagueSettings, Player, Recommendation, UserAdjustment } from '../types'

export interface RecommendationRequest {
  players: Player[]
  picks: DraftPick[]
  keepers: KeeperAssignment[]
  settings: LeagueSettings
  adjustments: UserAdjustment[]
}

export interface RecommendationResponse {
  recommendations: Recommendation[]
  count: number
}

export interface ImportCsvResponse {
  players: Player[]
  warnings: Array<string | { row: number; message: string }>
  adjustments: UserAdjustment[]
}

interface EngineRecommendation {
  player_id: string
  player_name: string
  position: Player['position']
  dvs_score: number
  tier_label: Recommendation['tierLabel']
  breakdown: {
    vorp: number
    marginal_value: number
    wait_loss: number
    tier_urgency: number
    survival_probability: number
    need_multiplier: number
    opponent_demand_factor: number
    guardrail_adjustment: number
    projected_points?: number
    immediate_value?: number
    adjusted_survival_probability?: number
    expected_fallback_value?: number
    tier_cliff?: number
    players_remaining_in_tier?: number
    tier_exhaustion?: number
    tier_opportunity_cost?: number
    opponent_need_factor?: number
    run_pressure?: number
    expected_next_pick_value?: number
    two_pick_path_value?: number
    shape_adjustment?: number
    decision_score?: number
  }
  reasons: string[]
}

export function buildReservedRosters(keepers: KeeperAssignment[] = []): Record<string, string[]> {
  const result: Record<string, string[]> = {}
  for (const keeper of keepers) {
    const key = String(keeper.teamId)
    result[key] ??= []
    result[key].push(keeper.playerId)
  }
  return result
}

export function serializeRecommendationRequest(request: RecommendationRequest) {
  const reservedRosters = buildReservedRosters(request.keepers ?? [])
  return {
    players: request.players,
    settings: {
      teamCount: request.settings.teamCount,
      rosterSlots: request.settings.rosterSlots,
      scoringFormat: request.settings.scoring === 'HALF_PPR'
        ? 'halfPPR'
        : request.settings.scoring === 'STANDARD' ? 'standard' : 'PPR',
      draftType: 'snake',
      leagueType: 'redraft',
      userTeamId: String(request.settings.userTeam),
      formulaVersion: request.settings.formulaVersion ?? 4
    },
    draftState: {
      teamCount: request.settings.teamCount,
      pickHistory: request.picks.map((pick) => ({
        eventId: pick.id,
        pickNumber: pick.pickNumber,
        teamId: String(pick.teamId),
        playerId: pick.playerId,
        timestamp: new Date(pick.timestamp).toISOString()
      })),
      reservedRosters
    },
    adjustments: request.adjustments,
    limit: 20
  }
}

export function normalizeRecommendations(results: EngineRecommendation[]): Recommendation[] {
  return results.map((result) => ({
    playerId: result.player_id,
    playerName: result.player_name,
    position: result.position,
    dvsScore: result.dvs_score,
    tierLabel: result.tier_label,
    breakdown: {
      vorp: result.breakdown.vorp,
      marginalValue: result.breakdown.marginal_value ?? 0,
      waitLoss: result.breakdown.wait_loss ?? 0,
      tierUrgency: result.breakdown.tier_urgency,
      survivalProbability: result.breakdown.survival_probability,
      needMultiplier: result.breakdown.need_multiplier,
      opponentDemandFactor: result.breakdown.opponent_demand_factor,
      guardrailAdjustment: result.breakdown.guardrail_adjustment,
      projectedPoints: result.breakdown.projected_points,
      immediateValue: result.breakdown.immediate_value ?? result.breakdown.marginal_value ?? 0,
      adjustedSurvivalProbability: result.breakdown.adjusted_survival_probability ?? result.breakdown.survival_probability,
      expectedFallbackValue: result.breakdown.expected_fallback_value,
      tierCliff: result.breakdown.tier_cliff,
      playersRemainingInTier: result.breakdown.players_remaining_in_tier,
      tierExhaustion: result.breakdown.tier_exhaustion,
      tierOpportunityCost: result.breakdown.tier_opportunity_cost ?? result.breakdown.tier_urgency,
      opponentNeedFactor: result.breakdown.opponent_need_factor ?? result.breakdown.opponent_demand_factor,
      runPressure: result.breakdown.run_pressure,
      expectedNextPickValue: result.breakdown.expected_next_pick_value,
      twoPickPathValue: result.breakdown.two_pick_path_value,
      shapeAdjustment: result.breakdown.shape_adjustment,
      decisionScore: result.breakdown.decision_score ?? result.dvs_score
    },
    reasons: result.reasons,
    explanation: result.reasons.join(' · ') || 'Best available value for the current draft state.'
  }))
}

export class DraftApiClient {
  constructor(private readonly baseUrl = '') {}

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      signal: init.signal ?? AbortSignal.timeout(4_000)
    })
    if (!response.ok) throw new Error(`Draft API request failed (${response.status})`)
    return response.json() as Promise<T>
  }

  recommendations(body: RecommendationRequest) {
    return this.request<{ recommendations: EngineRecommendation[]; count: number }>('/api/v1/recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(serializeRecommendationRequest(body))
    }).then((response) => ({
      recommendations: normalizeRecommendations(response.recommendations),
      count: response.count
    }))
  }

  async importCsv(file: File) {
    return this.request<ImportCsvResponse>('/api/v1/imports/csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: await file.text(), strict: false })
    })
  }
}

export const draftApi = new DraftApiClient(
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
)
