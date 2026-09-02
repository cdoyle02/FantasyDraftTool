export type PlayerPosition = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DST'
export type Position = PlayerPosition | 'FLEX' | 'SUPERFLEX'
export type ScoringFormat = 'PPR' | 'HALF_PPR' | 'STANDARD'

export interface FootballersSourceTags {
  myGuy?: boolean
  value?: boolean
  bust?: boolean
  sleeper?: boolean
  rookie?: boolean
  injured?: boolean
  breakout?: boolean
}

export interface PlayerImportSource {
  season: number
  asOfDate: string
  rankingType: string
  scoringProfile: string
  leagueSize: number
  sourceCheatsheetId: string
  sourceUrl?: string
  fingerprint: string
}

export interface Player {
  id: string
  name: string
  position: PlayerPosition
  team: string
  projectedPoints: number
  adp?: number
  espnAdp?: number
  sleeperAdp?: number
  tier: number
  depthChartRank?: number
  depthChartSource?: string
  upsideScore?: number
  riskScore?: number
  isRookie?: boolean
  isBreakout?: boolean
  injuryStatus?: string
  irEligible?: boolean
  expectedReturnWeek?: number
  byeWeek?: number
  positionRank?: number
  tierRank?: number
  tierSize?: number
  tierValueMultiplier?: number
  adpRoundPick?: string
  playerSlug?: string
  sourceTags?: FootballersSourceTags
  sourceTagsRaw?: string
  importSource?: PlayerImportSource
}

export interface UserAdjustment {
  playerId: string
  pointsDelta: number
  tierOverride?: number
  tag?: 'myGuy' | 'avoid' | 'irStash'
  note?: string
}

export interface LeagueSettings {
  name: string
  teamCount: number
  userTeam: number
  rosterSlots: Record<Position | 'BENCH', number>
  scoring: ScoringFormat
  draftType: 'SNAKE'
  formulaVersion?: number
  keeperSlots?: number
  irSlots?: number
}

export interface DraftPick {
  id: string
  pickNumber: number
  teamId: number
  playerId: string
  playerName: string
  position: Player['position']
  timestamp: number
  isKeeper?: boolean
}

export interface KeeperAssignment {
  id: string
  teamId: number
  playerId: string
  playerName: string
  position: Player['position']
  roundCost: 1
  timestamp: number
}

export interface ScoreBreakdown {
  vorp: number
  marginalValue: number
  waitLoss: number
  tierUrgency: number
  survivalProbability: number
  needMultiplier: number
  opponentDemandFactor: number
  guardrailAdjustment: number
  projectedPoints?: number
  immediateValue?: number
  adjustedSurvivalProbability?: number
  expectedFallbackValue?: number
  tierCliff?: number
  playersRemainingInTier?: number
  tierExhaustion?: number
  tierOpportunityCost?: number
  opponentNeedFactor?: number
  runPressure?: number
  expectedNextPickValue?: number
  twoPickPathValue?: number
  shapeAdjustment?: number
  decisionScore?: number
  lateRoundUpside?: number
  contingentValue?: number
  handcuffBonus?: number
  irStashValue?: number
  optionalityValue?: number
  specialTeamsTimingPenalty?: number
  specialTeamsPositionCap?: boolean
  latePhaseWeight?: number
  starterCompletion?: number
  starterSlotsFilled?: number
  starterSlotsTotal?: number
  replacementLevel?: number
}

export interface Recommendation {
  playerId: string
  playerName?: string
  position?: Player['position']
  dvsScore: number
  tierLabel: "CAN'T PASS" | 'BEST PICK' | 'SAFE TO WAIT'
  breakdown: ScoreBreakdown
  explanation: string
  reasons?: string[]
}

export type EngineMode = 'online-api' | 'offline-python' | 'development-fallback'

export interface FormulaConfigurationSnapshot {
  formulaVersion: number | null
  oneTurnSims: number | null
  simulationSeed: number | null
  formulaParams: Record<string, unknown> | null
}

export interface RecommendationGenerationContext extends FormulaConfigurationSnapshot {
  engineMode: EngineMode
  engineWarning?: string
  generatedAt: number
  generatedForPickIds: string[]
  generatedForPickCount: number
}

export interface EvaluationRecommendation {
  rank: number
  player: Player
  dvsScore: number
  decisionScore: number
  tierLabel: Recommendation['tierLabel']
  breakdown: ScoreBreakdown
  reasonStrings: string[]
}

export interface EvaluationRevision {
  type: 'CORRECTED' | 'UNDONE' | 'REMOVED'
  timestamp: number
  previousSelection: Player
  nextSelection?: Player
}

export interface DraftEvaluationRecord {
  id: string
  pickId: string
  pickNumber: number
  round: number
  capturedAt: number
  status: 'active' | 'undone' | 'removed'
  userRoster: DraftPick[]
  availablePlayerPool: Player[]
  topRecommendations: EvaluationRecommendation[]
  recommendationGeneration: RecommendationGenerationContext
  recommendationsMatchBoardState: boolean
  actualSelection: Player
  actualSelectionRecommendationRank: number | null
  actualSelectionDecisionScore: number | null
  actualSelectionScoreBreakdown: ScoreBreakdown | null
  boardState: {
    settings: LeagueSettings
    picks: DraftPick[]
    keepers: KeeperAssignment[]
    adjustments: UserAdjustment[]
    players: Player[]
  }
  revisions: EvaluationRevision[]
}

export interface DraftEvaluationExport {
  schemaVersion: 2
  exportedAt: string
  finalState: {
    settings: LeagueSettings
    players: Player[]
    adjustments: Record<string, UserAdjustment>
    picks: DraftPick[]
    keepers: KeeperAssignment[]
  }
  evaluationRecords: DraftEvaluationRecord[]
}

export const defaultLeague: LeagueSettings = {
  name: 'Sunday League',
  teamCount: 12,
  userTeam: 6,
  rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0, BENCH: 6, K: 1, DST: 1 },
  scoring: 'PPR',
  draftType: 'SNAKE',
  formulaVersion: 4
}
