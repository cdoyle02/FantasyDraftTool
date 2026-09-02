import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Player, Recommendation } from '../types'

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
const keepersTable = {
  toArray: vi.fn().mockResolvedValue([]),
  put: vi.fn(),
  delete: vi.fn(),
  clear: vi.fn(),
  bulkPut: vi.fn()
}
const settingsTable = { get: vi.fn() }
const metaTable = { get: vi.fn(), put: vi.fn() }
const evaluationRecordsTable = {
  orderBy: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })),
  put: vi.fn()
}
const eventsTable = {}

vi.mock('../data/db', () => ({
  db: {
    players: playersTable,
    adjustments: adjustmentsTable,
    picks: picksTable,
    keepers: keepersTable,
    settings: settingsTable,
    meta: metaTable,
    evaluationRecords: evaluationRecordsTable,
    events: eventsTable,
    transaction: async (...args: unknown[]) => {
      const work = args.at(-1)
      if (typeof work !== 'function') throw new Error('Dexie transaction mock expected a callback')
      return work()
    }
  },
  queueEvent: vi.fn()
}))

vi.mock('../engine/adapter', () => ({
  getRecommendations: vi.fn().mockResolvedValue({
    recommendations: [],
    mode: 'development-fallback',
    configuration: {
      formulaVersion: 4,
      oneTurnSims: null,
      simulationSeed: null,
      formulaParams: null
    }
  }),
  prepareOfflineEngine: vi.fn().mockRejectedValue(new Error('offline skipped in unit test'))
}))

import { getRecommendations } from '../engine/adapter'

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

  it('groups each team roster from snake pick numbers, not stored teamId', async () => {
    const { rosterForTeam, roundForPick } = await import('./draftStore')
    const picks = [
      { id: '1', pickNumber: 1, teamId: 1, playerId: 'a', playerName: 'Alpha', position: 'RB' as const, timestamp: 1 },
      { id: '2', pickNumber: 2, teamId: 1, playerId: 'b', playerName: 'Bravo', position: 'WR' as const, timestamp: 2 },
      { id: '3', pickNumber: 3, teamId: 1, playerId: 'c', playerName: 'Charlie', position: 'TE' as const, timestamp: 3 },
      { id: '5', pickNumber: 5, teamId: 1, playerId: 'e', playerName: 'Echo', position: 'RB' as const, timestamp: 5 },
      { id: '8', pickNumber: 8, teamId: 1, playerId: 'h', playerName: 'Hotel', position: 'QB' as const, timestamp: 8 }
    ]
    expect(rosterForTeam(picks, 1, 4).map((pick) => pick.playerName)).toEqual(['Alpha', 'Hotel'])
    expect(rosterForTeam(picks, 2, 4).map((pick) => pick.playerName)).toEqual(['Bravo'])
    expect(rosterForTeam(picks, 4, 4).map((pick) => pick.playerName)).toEqual(['Echo'])
    expect(roundForPick(2, 4)).toBe(1)
    expect(roundForPick(5, 4)).toBe(2)
    expect(roundForPick(8, 4)).toBe(2)
  })
})

describe('hydrate seed versioning', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    adjustmentsTable.toArray.mockResolvedValue([])
    settingsTable.get.mockResolvedValue(undefined)
    metaTable.get.mockResolvedValue(undefined)
    evaluationRecordsTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    picksTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      players: [],
      adjustments: {},
      picks: [],
      keepers: [],
      recommendations: [],
      recommendationContext: undefined,
      evaluationRecords: [],
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

  it('assigns sequential picks to the next snake-order team', async () => {
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    picksTable.put.mockResolvedValue(undefined)
    useDraftStore.setState({
      players: demoPlayers,
      picks: [],
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 }
    })

    await useDraftStore.getState().draftPlayer(demoPlayers[0])
    await useDraftStore.getState().draftPlayer(demoPlayers[1])
    await useDraftStore.getState().draftPlayer(demoPlayers[2])

    expect(useDraftStore.getState().picks.map((pick) => pick.teamId)).toEqual([1, 2, 3])
  })

  it('assigns a keeper to a chosen team without advancing the draft clock', async () => {
    const { defaultLeague } = await import('../types')
    const { useDraftStore, rosterEntriesForTeam } = await import('./draftStore')
    keepersTable.put.mockResolvedValue(undefined)
    useDraftStore.setState({
      players: demoPlayers,
      picks: [],
      keepers: [],
      settings: { ...defaultLeague, teamCount: 12, userTeam: 6 }
    })

    await useDraftStore.getState().assignKeeper(demoPlayers[0], 6)

    expect(useDraftStore.getState().keepers).toHaveLength(1)
    expect(useDraftStore.getState().keepers[0].teamId).toBe(6)
    expect(useDraftStore.getState().picks).toHaveLength(0)
    expect(rosterEntriesForTeam([], useDraftStore.getState().keepers, 6, 12)[0].isKeeper).toBe(true)
  })

  it('rejects duplicate keeper assignments and returns the player after removal', async () => {
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    keepersTable.put.mockResolvedValue(undefined)
    keepersTable.delete.mockResolvedValue(undefined)
    useDraftStore.setState({
      players: demoPlayers,
      picks: [],
      keepers: [],
      settings: { ...defaultLeague, teamCount: 12, userTeam: 6 }
    })

    await useDraftStore.getState().assignKeeper(demoPlayers[0], 6)
    await useDraftStore.getState().assignKeeper(demoPlayers[0], 4)
    expect(useDraftStore.getState().keepers).toHaveLength(1)

    const keeperId = useDraftStore.getState().keepers[0].id
    await useDraftStore.getState().removeKeeper(keeperId)
    expect(useDraftStore.getState().keepers).toHaveLength(0)
  })

  it('filters kept players out of recommendation results', async () => {
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    vi.mocked(getRecommendations).mockResolvedValueOnce({
      recommendations: [{
        playerId: demoPlayers[0].id,
        dvsScore: 99,
        tierLabel: 'BEST PICK',
        breakdown: {
          vorp: 1,
          marginalValue: 1,
          waitLoss: 0,
          tierUrgency: 1,
          survivalProbability: 0.5,
          needMultiplier: 1,
          opponentDemandFactor: 1,
          guardrailAdjustment: 0
        },
        explanation: 'test'
      }],
      mode: 'development-fallback',
      configuration: {
        formulaVersion: 4,
        oneTurnSims: null,
        simulationSeed: null,
        formulaParams: null
      }
    })
    useDraftStore.setState({
      players: demoPlayers,
      picks: [],
      keepers: [{
        id: 'keeper-1',
        teamId: 6,
        playerId: demoPlayers[0].id,
        playerName: demoPlayers[0].name,
        position: demoPlayers[0].position,
        roundCost: 1,
        timestamp: 1
      }],
      settings: defaultLeague
    })

    await useDraftStore.getState().refreshRecommendations()

    expect(useDraftStore.getState().recommendations).toHaveLength(0)
  })

  it('reloads the bundled seed when stored players are missing ESPN ADP', async () => {
    const { seedPlayers } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    playersTable.toArray.mockResolvedValue(seedPlayers.map((player) => {
      const withoutAdp: Player = { ...player }
      delete withoutAdp.espnAdp
      delete withoutAdp.sleeperAdp
      return withoutAdp
    }))
    metaTable.get.mockResolvedValue({ id: 'seed', version: (await import('../data/seed')).SEED_VERSION })

    await useDraftStore.getState().hydrate()

    expect(playersTable.bulkPut).toHaveBeenCalledWith(seedPlayers)
    expect(useDraftStore.getState().players.some((player) => player.espnAdp != null)).toBe(true)
  })

  it('reloads the bundled seed when the stored version is stale', async () => {
    const { seedPlayers, SEED_VERSION } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    playersTable.toArray.mockResolvedValue(seedPlayers)
    metaTable.get.mockResolvedValue({ id: 'seed', version: 'old' })

    await useDraftStore.getState().hydrate()

    expect(playersTable.clear).toHaveBeenCalled()
    expect(playersTable.bulkPut).toHaveBeenCalledWith(seedPlayers)
    expect(metaTable.put).toHaveBeenCalledWith({ id: 'seed', version: SEED_VERSION })
  })

  it('leaves a matching bundled seed and a CSV import in place', async () => {
    const { seedPlayers, SEED_VERSION } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    playersTable.toArray.mockResolvedValue(seedPlayers)
    metaTable.get.mockResolvedValue({ id: 'seed', version: SEED_VERSION })

    await useDraftStore.getState().hydrate()

    expect(playersTable.clear).not.toHaveBeenCalled()
    expect(playersTable.bulkPut).not.toHaveBeenCalled()
    expect(useDraftStore.getState().players).toBe(seedPlayers)

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
    metaTable.get.mockResolvedValue({ id: 'seed', version: 'old' })

    await useDraftStore.getState().hydrate()

    expect(useDraftStore.getState().players).toEqual(csvPlayers)
  })
})

function recommendationFor(player: Player, score: number): Recommendation {
  return {
    playerId: player.id,
    playerName: player.name,
    position: player.position,
    dvsScore: score,
    tierLabel: 'BEST PICK',
    breakdown: {
      vorp: score - 10,
      marginalValue: score - 5,
      waitLoss: 3,
      tierUrgency: 2,
      tierOpportunityCost: 2,
      survivalProbability: 0.5,
      adjustedSurvivalProbability: 0.4,
      needMultiplier: 1,
      opponentDemandFactor: 1,
      guardrailAdjustment: 0,
      expectedNextPickValue: 20,
      shapeAdjustment: 1.5,
      decisionScore: score,
      lateRoundUpside: 1,
      handcuffBonus: 0,
      irStashValue: 0,
      latePhaseWeight: 0.25,
      replacementLevel: 150
    },
    reasons: [`Decision score ${score}`],
    explanation: `Decision score ${score}`
  }
}

describe('draft evaluation capture', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    const recommendations = demoPlayers.slice(0, 12).map((player, index) => recommendationFor(player, 100 - index))
    useDraftStore.setState({
      players: demoPlayers,
      adjustments: {},
      picks: [],
      keepers: [],
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 },
      recommendations,
      recommendationContext: {
        formulaVersion: 4,
        oneTurnSims: 48,
        simulationSeed: 2026,
        formulaParams: { one_turn_sims: 48, sim_seed: 2026 },
        engineMode: 'offline-python',
        generatedAt: 10,
        generatedForPickIds: [],
        generatedForPickCount: 0
      },
      evaluationRecords: [],
      engineMode: 'offline-python'
    })
  })

  it('captures a pre-pick snapshot only for the user team with explicit top-10 ranks', async () => {
    const { useDraftStore } = await import('./draftStore')

    await useDraftStore.getState().draftPlayer(demoPlayers[11])

    const [record] = useDraftStore.getState().evaluationRecords
    expect(record.pickNumber).toBe(1)
    expect(record.round).toBe(1)
    expect(record.userRoster).toEqual([])
    expect(record.availablePlayerPool).toHaveLength(demoPlayers.length)
    expect(record.boardState.picks).toEqual([])
    expect(record.topRecommendations.map((item) => item.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    expect(record.topRecommendations[0].player.adp).toBe(1)
    expect(record.topRecommendations[0].reasonStrings).toEqual(['Decision score 100'])
    expect(record.actualSelectionRecommendationRank).toBeNull()
    expect(record.actualSelectionDecisionScore).toBe(89)
    expect(record.actualSelectionScoreBreakdown?.decisionScore).toBe(89)
    expect(record.recommendationGeneration.oneTurnSims).toBe(48)
    expect(record.recommendationsMatchBoardState).toBe(true)
    expect(evaluationRecordsTable.put).toHaveBeenCalledWith(record)

    useDraftStore.setState({
      picks: [],
      evaluationRecords: [],
      settings: { ...useDraftStore.getState().settings, userTeam: 2 }
    })
    await useDraftStore.getState().draftPlayer(demoPlayers[0])
    expect(useDraftStore.getState().evaluationRecords).toEqual([])
  })

  it('retains correction and undo history for a user selection', async () => {
    const { useDraftStore } = await import('./draftStore')
    await useDraftStore.getState().draftPlayer(demoPlayers[0])
    const pickId = useDraftStore.getState().picks[0].id

    await useDraftStore.getState().correctPick(pickId, demoPlayers[1])
    let record = useDraftStore.getState().evaluationRecords[0]
    expect(record.actualSelection.id).toBe(demoPlayers[1].id)
    expect(record.actualSelectionRecommendationRank).toBe(2)
    expect(record.revisions[0]).toMatchObject({
      type: 'CORRECTED',
      previousSelection: { id: demoPlayers[0].id },
      nextSelection: { id: demoPlayers[1].id }
    })

    await useDraftStore.getState().undoLastPick()
    record = useDraftStore.getState().evaluationRecords[0]
    expect(record.status).toBe('undone')
    expect(record.revisions.at(-1)?.type).toBe('UNDONE')
  })
})
