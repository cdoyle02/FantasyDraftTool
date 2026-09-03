import type {
  DraftPick,
  FormulaConfigurationSnapshot,
  KeeperAssignment,
  LeagueSettings,
  Player,
  Recommendation,
  UserAdjustment
} from '../types'

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
  configuration: FormulaConfigurationSnapshot
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
    late_round_upside?: number
    contingent_value?: number
    handcuff_bonus?: number
    ir_stash_value?: number
    optionality_value?: number
    special_teams_timing_penalty?: number
    special_teams_position_cap?: boolean
    late_phase_weight?: number
    starter_completion?: number
    starter_slots_filled?: number
    starter_slots_total?: number
    replacement_level?: number
    negative_vorp_adjustment?: number
    raw_handcuff_bonus?: number
    adjusted_handcuff_bonus?: number
    own_handcuff_league_multiplier?: number
    own_handcuff_count?: number
    own_handcuff_count_multiplier?: number
    bench_balance_adjustment?: number
    usable_rb_depth?: number
    usable_wr_depth?: number
    roster_risk_score?: number
    pre_reliability_score?: number
    reliability_adjustment?: number
    v5_policy_strength?: number
  }
  reasons: string[]
}

interface EngineRecommendationResponse {
  recommendations: EngineRecommendation[]
  count?: number
  configuration?: {
    formulaVersion?: number
    oneTurnSims?: number
    simulationSeed?: number
    formulaParams?: Record<string, unknown>
  }
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
      formulaVersion: request.settings.formulaVersion ?? 4,
      keeperSlots: request.settings.keeperSlots ?? 0,
      irSlots: request.settings.irSlots ?? 0
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
      decisionScore: result.breakdown.decision_score ?? result.dvs_score,
      lateRoundUpside: result.breakdown.late_round_upside,
      contingentValue: result.breakdown.contingent_value,
      handcuffBonus: result.breakdown.handcuff_bonus,
      irStashValue: result.breakdown.ir_stash_value,
      optionalityValue: result.breakdown.optionality_value,
      specialTeamsTimingPenalty: result.breakdown.special_teams_timing_penalty,
      specialTeamsPositionCap: result.breakdown.special_teams_position_cap,
      latePhaseWeight: result.breakdown.late_phase_weight,
      starterCompletion: result.breakdown.starter_completion,
      starterSlotsFilled: result.breakdown.starter_slots_filled,
      starterSlotsTotal: result.breakdown.starter_slots_total,
      replacementLevel: result.breakdown.replacement_level,
      negativeVorpAdjustment: result.breakdown.negative_vorp_adjustment,
      rawHandcuffBonus: result.breakdown.raw_handcuff_bonus,
      adjustedHandcuffBonus: result.breakdown.adjusted_handcuff_bonus,
      ownHandcuffLeagueMultiplier: result.breakdown.own_handcuff_league_multiplier,
      ownHandcuffCount: result.breakdown.own_handcuff_count,
      ownHandcuffCountMultiplier: result.breakdown.own_handcuff_count_multiplier,
      benchBalanceAdjustment: result.breakdown.bench_balance_adjustment,
      usableRbDepth: result.breakdown.usable_rb_depth,
      usableWrDepth: result.breakdown.usable_wr_depth,
      rosterRiskScore: result.breakdown.roster_risk_score,
      preReliabilityScore: result.breakdown.pre_reliability_score,
      reliabilityAdjustment: result.breakdown.reliability_adjustment,
      v5PolicyStrength: result.breakdown.v5_policy_strength
    },
    reasons: result.reasons,
    explanation: result.reasons.join(' · ') || 'Best available value for the current draft state.'
  }))
}

export function normalizeRecommendationResponse(response: EngineRecommendationResponse): RecommendationResponse {
  return {
    recommendations: normalizeRecommendations(response.recommendations),
    count: response.count ?? response.recommendations.length,
    configuration: {
      formulaVersion: response.configuration?.formulaVersion ?? null,
      oneTurnSims: response.configuration?.oneTurnSims ?? null,
      simulationSeed: response.configuration?.simulationSeed ?? null,
      formulaParams: response.configuration?.formulaParams ?? null
    }
  }
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
    return this.request<EngineRecommendationResponse>('/api/v1/recommendations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(serializeRecommendationRequest(body))
    }).then(normalizeRecommendationResponse)
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
