import Dexie, { type EntityTable } from 'dexie'
import type { DraftPick, LeagueSettings, Player, UserAdjustment } from '../types'

export interface SeedMeta {
  id: 'seed'
  version: string
}

export interface QueueEvent {
  id: string
  type: 'PICK_CREATED' | 'PICK_UNDONE' | 'PICK_REMOVED' | 'PICK_CORRECTED' | 'PLAYER_ADJUSTED' | 'CSV_IMPORTED' | 'SETTINGS_UPDATED'
  payload: unknown
  createdAt: number
  status: 'pending' | 'synced'
}

class DraftDatabase extends Dexie {
  players!: EntityTable<Player, 'id'>
  picks!: EntityTable<DraftPick, 'id'>
  settings!: EntityTable<LeagueSettings & { id: string }, 'id'>
  adjustments!: EntityTable<UserAdjustment, 'playerId'>
  events!: EntityTable<QueueEvent, 'id'>
  meta!: EntityTable<SeedMeta, 'id'>

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
