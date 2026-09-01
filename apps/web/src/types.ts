export type PlayerPosition = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DST'
export type Position = PlayerPosition | 'FLEX' | 'SUPERFLEX'
export type ScoringFormat = 'PPR' | 'HALF_PPR' | 'STANDARD'

export interface Player {
  id: string
  name: string
  position: PlayerPosition
  team: string
  projectedPoints: number
  adp: number
  espnAdp?: number
  sleeperAdp?: number
  tier: number
}

export interface UserAdjustment {
  playerId: string
  pointsDelta: number
  tierOverride?: number
  tag?: 'myGuy' | 'avoid'
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
}

export interface DraftPick {
  id: string
  pickNumber: number
  teamId: number
  playerId: string
  playerName: string
  position: Player['position']
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

export const defaultLeague: LeagueSettings = {
  name: 'Sunday League',
  teamCount: 12,
  userTeam: 6,
  rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0, BENCH: 6, K: 1, DST: 1 },
  scoring: 'PPR',
  draftType: 'SNAKE',
  formulaVersion: 4
}
