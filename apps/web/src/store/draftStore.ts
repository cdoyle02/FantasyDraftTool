import { create } from 'zustand'
import { db, queueEvent } from '../data/db'
import { seedPlayers } from '../data/seed'
import type { DraftPick, LeagueSettings, Player, Recommendation, UserAdjustment } from '../types'
import { defaultLeague } from '../types'
import { getRecommendations, prepareOfflineEngine, type EngineMode } from '../engine/adapter'

interface DraftStore {
  players: Player[]
  adjustments: Record<string, UserAdjustment>
  picks: DraftPick[]
  settings: LeagueSettings
  recommendations: Recommendation[]
  engineMode: EngineMode
  engineWarning?: string
  offlineReady: boolean
  hydrated: boolean
  hydrate: () => Promise<void>
  importPlayers: (players: Player[]) => Promise<void>
  draftPlayer: (player: Player) => Promise<void>
  correctPick: (id: string, player: Player) => Promise<void>
  undoLastPick: () => Promise<void>
  removePick: (id: string) => Promise<void>
  adjustPlayer: (id: string, patch: Partial<Omit<UserAdjustment, 'playerId'>>) => Promise<void>
  updateSettings: (patch: Partial<LeagueSettings>) => Promise<void>
  refreshRecommendations: () => Promise<void>
}

export function teamForPick(pickNumber: number, teamCount: number) {
  const zero = pickNumber - 1
  const round = Math.floor(zero / teamCount)
  const slot = zero % teamCount
  return round % 2 === 0 ? slot + 1 : teamCount - slot
}

let recommendationRequestId = 0

export const useDraftStore = create<DraftStore>((set, get) => ({
  players: [],
  adjustments: {},
  picks: [],
  settings: defaultLeague,
  recommendations: [],
  engineMode: 'unavailable',
  offlineReady: false,
  hydrated: false,
  hydrate: async () => {
    const [storedPlayers, storedAdjustments, picks, storedSettings] = await Promise.all([
      db.players.toArray(),
      db.adjustments.toArray(),
      db.picks.orderBy('pickNumber').toArray(),
      db.settings.get('active')
    ])
    const players = storedPlayers.length ? storedPlayers : seedPlayers
    if (!storedPlayers.length) await db.players.bulkPut(players)
    set({
      players,
      adjustments: Object.fromEntries(storedAdjustments.map((item) => [item.playerId, item])),
      picks,
      settings: storedSettings ? { ...storedSettings, id: undefined } as unknown as LeagueSettings : defaultLeague,
      hydrated: true
    })
    await get().refreshRecommendations()
    try {
      await prepareOfflineEngine()
      set({ offlineReady: true })
    } catch (error) {
      set({
        offlineReady: false,
        engineWarning: `Offline Python engine is not ready: ${error instanceof Error ? error.message : 'preparation failed'}`
      })
    }
  },
  importPlayers: async (players) => {
    await db.transaction('rw', db.players, db.events, async () => {
      await db.players.clear()
      await db.players.bulkPut(players)
      await queueEvent('CSV_IMPORTED', { count: players.length })
    })
    set({ players })
    await get().refreshRecommendations()
  },
  draftPlayer: async (player) => {
    if (get().picks.some((pick) => pick.playerId === player.id)) return
    const totalRounds = Object.values(get().settings.rosterSlots).reduce((sum, count) => sum + count, 0)
    if (get().picks.length >= get().settings.teamCount * totalRounds) return
    const pickNumber = get().picks.length + 1
    const pick: DraftPick = {
      id: crypto.randomUUID(),
      pickNumber,
      teamId: teamForPick(pickNumber, get().settings.teamCount),
      playerId: player.id,
      playerName: player.name,
      position: player.position,
      timestamp: Date.now()
    }
    await db.picks.put(pick)
    await queueEvent('PICK_CREATED', pick)
    set((state) => ({ picks: [...state.picks, pick] }))
    await get().refreshRecommendations()
  },
  correctPick: async (id, player) => {
    const current = get().picks.find((pick) => pick.id === id)
    if (!current || get().picks.some((pick) => pick.id !== id && pick.playerId === player.id)) return
    const corrected: DraftPick = {
      ...current,
      playerId: player.id,
      playerName: player.name,
      position: player.position,
      timestamp: Date.now()
    }
    await db.picks.put(corrected)
    await queueEvent('PICK_CORRECTED', { before: current, after: corrected })
    set((state) => ({ picks: state.picks.map((pick) => pick.id === id ? corrected : pick) }))
    await get().refreshRecommendations()
  },
  undoLastPick: async () => {
    const last = get().picks.at(-1)
    if (!last) return
    await db.picks.delete(last.id)
    await queueEvent('PICK_UNDONE', last)
    set((state) => ({ picks: state.picks.slice(0, -1) }))
    await get().refreshRecommendations()
  },
  removePick: async (id) => {
    const removed = get().picks.find((pick) => pick.id === id)
    const remaining = get().picks.filter((pick) => pick.id !== id).map((pick, index) => ({
      ...pick,
      pickNumber: index + 1,
      teamId: teamForPick(index + 1, get().settings.teamCount)
    }))
    await db.transaction('rw', db.picks, async () => {
      await db.picks.clear()
      await db.picks.bulkPut(remaining)
    })
    if (removed) await queueEvent('PICK_REMOVED', removed)
    set({ picks: remaining })
    await get().refreshRecommendations()
  },
  adjustPlayer: async (id, patch) => {
    if (!get().players.some((item) => item.id === id)) return
    const previous = get().adjustments[id]
    const updated: UserAdjustment = {
      ...previous,
      ...patch,
      playerId: id,
      pointsDelta: patch.pointsDelta ?? previous?.pointsDelta ?? 0
    }
    await db.adjustments.put(updated)
    await queueEvent('PLAYER_ADJUSTED', { id, patch })
    set((state) => ({ adjustments: { ...state.adjustments, [id]: updated } }))
    await get().refreshRecommendations()
  },
  updateSettings: async (patch) => {
    const next = { ...get().settings, ...patch }
    const settings = {
      ...next,
      teamCount: Math.max(4, Math.min(20, next.teamCount)),
      userTeam: Math.max(1, Math.min(next.teamCount, next.userTeam))
    }
    await db.settings.put({ ...settings, id: 'active' })
    await queueEvent('SETTINGS_UPDATED', patch)
    set({ settings })
    await get().refreshRecommendations()
  },
  refreshRecommendations: async () => {
    const { players, adjustments, picks, settings } = get()
    if (!players.length) return
    const requestId = ++recommendationRequestId
    const result = await getRecommendations({ players, adjustments: Object.values(adjustments), picks, settings })
    if (requestId !== recommendationRequestId) return
    set({ recommendations: result.recommendations, engineMode: result.mode, engineWarning: result.warning })
  }
}))
