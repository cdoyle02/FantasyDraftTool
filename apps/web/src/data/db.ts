import Dexie, { type EntityTable } from 'dexie'
import type { DraftEvaluationRecord, DraftPick, KeeperAssignment, LeagueSettings, Player, UserAdjustment } from '../types'
import type { SavedRankingProfile } from './savedRankings'

export interface SeedMeta {
  id: 'seed'
  version: string
}

export interface ImportMeta {
  id: 'import'
  fingerprint: string
  season: number
  asOfDate: string
  rankingType: string
  scoringProfile: string
  leagueSize: number
  sourceCheatsheetId: string
  sourceUrl?: string
  importedAt: number
  playerCount: number
  positionCounts: Record<string, number>
  savedProfileId?: string
  savedProfileName?: string
}

export interface QueueEvent {
  id: string
  type: 'PICK_CREATED' | 'PICK_UNDONE' | 'PICK_REMOVED' | 'PICK_CORRECTED' | 'KEEPER_ASSIGNED' | 'KEEPER_REMOVED' | 'PLAYER_ADJUSTED' | 'CSV_IMPORTED' | 'SETTINGS_UPDATED' | 'DRAFT_RESET'
  payload: unknown
  createdAt: number
  status: 'pending' | 'synced'
}

class DraftDatabase extends Dexie {
  players!: EntityTable<Player, 'id'>
  picks!: EntityTable<DraftPick, 'id'>
  keepers!: EntityTable<KeeperAssignment, 'id'>
  settings!: EntityTable<LeagueSettings & { id: string }, 'id'>
  adjustments!: EntityTable<UserAdjustment, 'playerId'>
  evaluationRecords!: EntityTable<DraftEvaluationRecord, 'id'>
  events!: EntityTable<QueueEvent, 'id'>
  meta!: EntityTable<SeedMeta, 'id'>
  importMeta!: EntityTable<ImportMeta, 'id'>
  savedRankings!: EntityTable<SavedRankingProfile, 'id'>

  constructor() {
    super('fantasy-draft-tool')
    this.version(1).stores({
      players: 'id, name, position, adp, tag',
      picks: 'id, pickNumber, teamId, playerId',
      settings: 'id',
      events: 'id, status, createdAt'
    })
    this.version(2).stores({
      players: 'id, name, position, adp',
      picks: 'id, pickNumber, teamId, playerId',
      settings: 'id',
      adjustments: 'playerId, tag',
      events: 'id, status, createdAt'
    })
    this.version(3).stores({
      players: 'id, name, position, adp',
      picks: 'id, pickNumber, teamId, playerId',
      settings: 'id',
      adjustments: 'playerId, tag',
      events: 'id, status, createdAt',
      meta: 'id'
    })
    this.version(4).stores({
      players: 'id, name, position, adp',
      picks: 'id, pickNumber, teamId, playerId',
      keepers: 'id, teamId, playerId',
      settings: 'id',
      adjustments: 'playerId, tag',
      events: 'id, status, createdAt',
      meta: 'id'
    })
    this.version(5).stores({
      players: 'id, name, position, adp',
      picks: 'id, pickNumber, teamId, playerId',
      keepers: 'id, teamId, playerId',
      settings: 'id',
      adjustments: 'playerId, tag',
      evaluationRecords: 'id, pickId, pickNumber, status, capturedAt',
      events: 'id, status, createdAt',
      meta: 'id'
    })
    this.version(6).stores({
      players: 'id, name, position, adp',
      picks: 'id, pickNumber, teamId, playerId',
      keepers: 'id, teamId, playerId',
      settings: 'id',
      adjustments: 'playerId, tag',
      evaluationRecords: 'id, pickId, pickNumber, status, capturedAt',
      events: 'id, status, createdAt',
      meta: 'id',
      importMeta: 'id'
    })
    this.version(7).stores({
      players: 'id, name, position, adp',
      picks: 'id, pickNumber, teamId, playerId',
      keepers: 'id, teamId, playerId',
      settings: 'id',
      adjustments: 'playerId, tag',
      evaluationRecords: 'id, pickId, pickNumber, status, capturedAt',
      events: 'id, status, createdAt',
      meta: 'id',
      importMeta: 'id',
      savedRankings: 'id, normalizedName, updatedAt'
    })
  }
}

export const db = new DraftDatabase()

export async function queueEvent(type: QueueEvent['type'], payload: unknown) {
  await db.events.put({
    id: crypto.randomUUID(),
    type,
    payload,
    createdAt: Date.now(),
    status: 'pending'
  })
}
