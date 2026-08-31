import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Player } from '../types'

const playersTable = {
  toArray: vi.fn(),
  bulkPut: vi.fn(),
  clear: vi.fn()
}
const adjustmentsTable = { toArray: vi.fn() }
const picksTable = {
  orderBy: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })),
  put: vi.fn(),
  delete: vi.fn(),
  clear: vi.fn(),
  bulkPut: vi.fn()
}
const settingsTable = { get: vi.fn() }
const metaTable = { get: vi.fn(), put: vi.fn() }

vi.mock('../data/db', () => ({
  db: {
    players: playersTable,
    adjustments: adjustmentsTable,
    picks: picksTable,
    settings: settingsTable,
    meta: metaTable,
    transaction: async (...args: unknown[]) => {
      const work = args.at(-1)
      if (typeof work !== 'function') throw new Error('Dexie transaction mock expected a callback')
      return work()
    }
  },
  queueEvent: vi.fn()
}))

vi.mock('../engine/adapter', () => ({
  getRecommendations: vi.fn().mockResolvedValue({ recommendations: [], mode: 'development-fallback' }),
  prepareOfflineEngine: vi.fn().mockRejectedValue(new Error('offline skipped in unit test'))
}))

const demoPlayers: Player[] = Array.from({ length: 25 }, (_, index) => ({
  id: `seed-${index + 1}`,
  name: `Demo ${index + 1}`,
  position: 'RB',
  team: 'ATL',
  projectedPoints: 200,
  adp: index + 1,
  tier: 1
}))

describe('snake draft order', () => {
  it('reverses team order on alternating rounds', async () => {
    const { teamForPick } = await import('./draftStore')
    expect(Array.from({ length: 12 }, (_, index) => teamForPick(index + 1, 12))).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    expect(Array.from({ length: 12 }, (_, index) => teamForPick(index + 13, 12))).toEqual([12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
    expect(teamForPick(25, 12)).toBe(1)
  })

})

describe('hydrate seed versioning', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    adjustmentsTable.toArray.mockResolvedValue([])
    settingsTable.get.mockResolvedValue(undefined)
    picksTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      players: [],
      adjustments: {},
      picks: [],
      recommendations: [],
      hydrated: false,
      offlineReady: false
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads the bundled rankings when IndexedDB is empty', async () => {
    const { seedPlayers } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    playersTable.toArray.mockResolvedValue([])

    await useDraftStore.getState().hydrate()

    expect(playersTable.bulkPut).toHaveBeenCalledWith(seedPlayers)
    expect(metaTable.put).toHaveBeenCalledWith({ id: 'seed', version: expect.any(String) })
    expect(useDraftStore.getState().players).toHaveLength(seedPlayers.length)
  })

  it('auto-replaces the 25-player demo and leaves a user CSV import alone', async () => {
    const { seedPlayers } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    playersTable.toArray.mockResolvedValue(demoPlayers)

    await useDraftStore.getState().hydrate()

    expect(playersTable.clear).toHaveBeenCalled()
    expect(playersTable.bulkPut).toHaveBeenCalledWith(seedPlayers)
    expect(useDraftStore.getState().players[0].id).not.toMatch(/^seed-\d+$/)

    const csvPlayers: Player[] = [{
      id: 'csv-bijan-robinson-rb-atl',
      name: 'Bijan Robinson',
      position: 'RB',
      team: 'ATL',
      projectedPoints: 300,
      adp: 4.2,
      tier: 1
    }]
    playersTable.toArray.mockResolvedValue(csvPlayers)
    playersTable.clear.mockClear()
    playersTable.bulkPut.mockClear()

    await useDraftStore.getState().hydrate()

    expect(playersTable.clear).not.toHaveBeenCalled()
    expect(playersTable.bulkPut).not.toHaveBeenCalled()
    expect(useDraftStore.getState().players).toEqual(csvPlayers)
  })

  it('reloading the bundle keeps adjustments in place', async () => {
    const { useDraftStore } = await import('./draftStore')
    const { seedPlayers } = await import('../data/seed')
    useDraftStore.setState({
      players: seedPlayers,
      adjustments: {
        [seedPlayers[0].id]: { playerId: seedPlayers[0].id, pointsDelta: 8, tag: 'myGuy' }
      }
    })

    await useDraftStore.getState().loadBundledRankings()

    expect(useDraftStore.getState().adjustments[seedPlayers[0].id]).toEqual({
      playerId: seedPlayers[0].id,
      pointsDelta: 8,
      tag: 'myGuy'
    })
    expect(useDraftStore.getState().players).toHaveLength(seedPlayers.length)
  })
})
