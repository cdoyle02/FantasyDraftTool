import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Player, Recommendation } from '../types'

const {
  playersTable,
  adjustmentsTable,
  picksTable,
  keepersTable,
  settingsTable,
  metaTable,
  importMetaTable,
  savedRankingsTable,
  evaluationRecordsTable,
  eventsTable
} = vi.hoisted(() => ({
  playersTable: {
    toArray: vi.fn(),
    bulkPut: vi.fn(),
    clear: vi.fn()
  },
  adjustmentsTable: { toArray: vi.fn() },
  picksTable: {
    orderBy: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })),
    put: vi.fn(),
    delete: vi.fn(),
    clear: vi.fn(),
    bulkPut: vi.fn()
  },
  keepersTable: {
    toArray: vi.fn().mockResolvedValue([]),
    put: vi.fn(),
    delete: vi.fn(),
    clear: vi.fn(),
    bulkPut: vi.fn()
  },
  settingsTable: { get: vi.fn(), put: vi.fn() },
  metaTable: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
  importMetaTable: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
  savedRankingsTable: {
    get: vi.fn(),
    put: vi.fn(),
    orderBy: vi.fn(() => ({ reverse: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })) }))
  },
  evaluationRecordsTable: {
    orderBy: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })),
    put: vi.fn(),
    clear: vi.fn()
  },
  eventsTable: {}
}))

vi.mock('../data/db', () => ({
  db: {
    players: playersTable,
    adjustments: adjustmentsTable,
    picks: picksTable,
    keepers: keepersTable,
    settings: settingsTable,
    meta: metaTable,
    importMeta: importMetaTable,
    savedRankings: savedRankingsTable,
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
    metaTable.get.mockImplementation(async (id: string) => (id === 'seed' ? undefined : undefined))
    importMetaTable.get.mockResolvedValue(undefined)
    savedRankingsTable.orderBy.mockReturnValue({ reverse: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })) })
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
      offlineReady: false,
      savedRankings: [],
      activeSavedProfileId: undefined
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

describe('resetDraft', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      players: demoPlayers,
      adjustments: { 'seed-1': { playerId: 'seed-1', pointsDelta: 5 } },
      picks: [],
      keepers: [],
      settings: { ...defaultLeague, teamCount: 4, userTeam: 2 },
      recommendations: [],
      recommendationContext: undefined,
      evaluationRecords: [],
      engineMode: 'development-fallback'
    })
  })

  it('clears draft progress and restores the bundled player pool', async () => {
    const { seedPlayers } = await import('../data/seed')
    const { queueEvent } = await import('../data/db')
    const { useDraftStore } = await import('./draftStore')
    const csvPlayers: Player[] = [{
      id: 'csv-1',
      name: 'CSV Player',
      position: 'RB',
      team: 'KC',
      projectedPoints: 100,
      adp: 1,
      tier: 1
    }]
    const settings = useDraftStore.getState().settings
    const adjustments = useDraftStore.getState().adjustments

    await useDraftStore.getState().draftPlayer(demoPlayers[0])
    await useDraftStore.getState().draftPlayer(demoPlayers[1])
    await useDraftStore.getState().assignKeeper(demoPlayers[2], 1)
    useDraftStore.setState({ players: csvPlayers })

    await useDraftStore.getState().resetDraft()

    expect(useDraftStore.getState().picks).toEqual([])
    expect(useDraftStore.getState().keepers).toEqual([])
    expect(useDraftStore.getState().evaluationRecords).toEqual([])
    expect(useDraftStore.getState().players).toEqual(seedPlayers)
    expect(useDraftStore.getState().settings).toEqual(settings)
    expect(useDraftStore.getState().adjustments).toEqual(adjustments)
    expect(picksTable.clear).toHaveBeenCalled()
    expect(keepersTable.clear).toHaveBeenCalled()
    expect(evaluationRecordsTable.clear).toHaveBeenCalled()
    expect(playersTable.clear).toHaveBeenCalled()
    expect(playersTable.bulkPut).toHaveBeenCalledWith(seedPlayers)
    expect(queueEvent).toHaveBeenLastCalledWith('DRAFT_RESET', {
      pickCount: 2,
      keeperCount: 1,
      evaluationCount: 1,
      playerCount: seedPlayers.length
    })
    expect(getRecommendations).toHaveBeenCalledWith(expect.objectContaining({
      picks: [],
      keepers: [],
      players: seedPlayers
    }))
  })

  it('is a no-op when the draft is already empty and the pool is bundled', async () => {
    const { seedPlayers } = await import('../data/seed')
    const { queueEvent } = await import('../data/db')
    const { useDraftStore } = await import('./draftStore')

    useDraftStore.setState({ players: seedPlayers, picks: [], keepers: [], evaluationRecords: [] })
    vi.mocked(queueEvent).mockClear()

    await useDraftStore.getState().resetDraft()

    expect(queueEvent).not.toHaveBeenCalled()
    expect(picksTable.clear).not.toHaveBeenCalled()
    expect(playersTable.clear).not.toHaveBeenCalled()
  })
})

describe('Footballers CSV import store flow', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    adjustmentsTable.toArray.mockResolvedValue([])
    settingsTable.get.mockResolvedValue(undefined)
    metaTable.get.mockImplementation(async (id: string) => (id === 'seed' ? { id: 'seed', version: '2026.6' } : undefined))
    importMetaTable.get.mockResolvedValue(undefined)
    savedRankingsTable.orderBy.mockReturnValue({ reverse: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })) })
    evaluationRecordsTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    picksTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      players: [],
      adjustments: {},
      picks: [],
      keepers: [],
      settings: {
        ...defaultLeague,
        teamCount: 8,
        rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 2, SUPERFLEX: 0, BENCH: 6, K: 0, DST: 1 }
      },
      recommendations: [{ playerId: 'old', dvsScore: 1, tierLabel: 'BEST PICK', breakdown: { vorp: 0, marginalValue: 0, waitLoss: 0, tierUrgency: 0, survivalProbability: 0, needMultiplier: 1, opponentDemandFactor: 1, guardrailAdjustment: 0 }, explanation: 'old' }],
      recommendationContext: {
        formulaVersion: 4,
        oneTurnSims: null,
        simulationSeed: null,
        formulaParams: null,
        engineMode: 'development-fallback',
        generatedAt: 1,
        generatedForPickIds: [],
        generatedForPickCount: 0
      },
      evaluationRecords: [{ id: 'eval-1' } as never],
      hydrated: true,
      importIdentity: undefined,
      savedRankings: [],
      activeSavedProfileId: undefined
    })
  })

  it('blocks import preparation when draft picks exist', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      picks: [{
        id: 'pick-1',
        pickNumber: 1,
        teamId: 1,
        playerId: 'josh-allen-buf-qb',
        playerName: 'Josh Allen',
        position: 'QB',
        timestamp: 1
      }]
    })
    const result = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.errors[0]?.message).toContain('draft picks exist')
  })

  it('commits League B atomically and clears derived evaluation state', async () => {
    const { buildFootballersCsv, leagueARows, leagueBRows } = await import('../data/footballersImport.fixtures')
    const { queueEvent } = await import('../data/db')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    expect(leagueA.ok).toBe(true)
    if (!leagueA.ok) return
    await useDraftStore.getState().commitFootballersImport(leagueA)
    const leagueB = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' })
    )
    expect(leagueB.ok).toBe(true)
    if (!leagueB.ok) return
    await useDraftStore.getState().commitFootballersImport(leagueB)
    const josh = useDraftStore.getState().players.find((player) => player.id === 'josh-allen-buf-qb')
    expect(josh?.tier).toBe(2)
    expect(useDraftStore.getState().evaluationRecords).toEqual([])
    expect(useDraftStore.getState().recommendationContext?.generatedForPickIds).toEqual([])
    expect(importMetaTable.put).toHaveBeenCalledWith(expect.objectContaining({ id: 'import', fingerprint: leagueB.identity.fingerprint }))
    expect(queueEvent).toHaveBeenLastCalledWith('CSV_IMPORTED', expect.objectContaining({ fingerprint: leagueB.identity.fingerprint }))
  })

  it('preserves League A when League B preparation fails', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    expect(leagueA.ok).toBe(true)
    if (!leagueA.ok) return
    await useDraftStore.getState().commitFootballersImport(leagueA)
    const before = useDraftStore.getState()
    const invalid = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueARows(), { sourceCheatsheetId: 'sheet-c', leagueSize: 10 })
    )
    expect(invalid.ok).toBe(false)
    const after = useDraftStore.getState()
    expect(after.players).toEqual(before.players)
    expect(after.importIdentity).toEqual(before.importIdentity)
    expect(after.evaluationRecords).toEqual(before.evaluationRecords)
  })

  it('survives keeper and adjustment references when stable IDs rematch', async () => {
    const { buildFootballersCsv, leagueARows, leagueBRows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    if (!leagueA.ok) throw new Error('league A failed')
    useDraftStore.setState({
      keepers: [{
        id: 'keeper-1',
        teamId: 1,
        playerId: 'josh-allen-buf-qb',
        playerName: 'Josh Allen',
        position: 'QB',
        roundCost: 1,
        timestamp: 1
      }],
      adjustments: {
        'josh-allen-buf-qb': { playerId: 'josh-allen-buf-qb', pointsDelta: 4, tag: 'myGuy' }
      }
    })
    const leagueB = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' })
    )
    expect(leagueB.ok).toBe(true)
    if (!leagueB.ok) return
    await useDraftStore.getState().commitFootballersImport(leagueB)
    expect(useDraftStore.getState().keepers[0]?.playerId).toBe('josh-allen-buf-qb')
    expect(useDraftStore.getState().adjustments['josh-allen-buf-qb']?.pointsDelta).toBe(4)
  })

  it('reports keeper conflicts when the imported pool drops a referenced player', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      keepers: [{
        id: 'keeper-1',
        teamId: 1,
        playerId: 'missing-player-id',
        playerName: 'Missing',
        position: 'RB',
        roundCost: 1,
        timestamp: 1
      }]
    })
    const result = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.errors.some((error) => error.message.includes('Keeper Missing'))).toBe(true)
  })
})

describe('active rankings badge invariant', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    adjustmentsTable.toArray.mockResolvedValue([])
    settingsTable.get.mockResolvedValue(undefined)
    metaTable.get.mockImplementation(async (id: string) => (id === 'seed' ? { id: 'seed', version: '2026.6' } : undefined))
    importMetaTable.get.mockResolvedValue(undefined)
    savedRankingsTable.orderBy.mockReturnValue({ reverse: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) })) })
    evaluationRecordsTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    picksTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      players: [],
      adjustments: {},
      picks: [],
      keepers: [],
      settings: {
        ...defaultLeague,
        teamCount: 8,
        rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 2, SUPERFLEX: 0, BENCH: 6, K: 0, DST: 1 }
      },
      recommendations: [],
      recommendationContext: undefined,
      evaluationRecords: [],
      hydrated: true,
      importIdentity: undefined,
      savedRankings: [],
      activeSavedProfileId: undefined
    })
  })

  it('keeps importIdentity aligned with the active imported player pool after commit', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const prepared = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    expect(prepared.ok).toBe(true)
    if (!prepared.ok) return
    await useDraftStore.getState().commitFootballersImport(prepared)

    const { importIdentity, players } = useDraftStore.getState()
    expect(importIdentity?.scoringProfile).toBe('Two Flex Too Furious')
    expect(importIdentity?.fingerprint).toBe(prepared.identity.fingerprint)
    expect(players.every((player) => player.importSource?.fingerprint === importIdentity?.fingerprint)).toBe(true)
    expect(importMetaTable.put).toHaveBeenCalledWith(expect.objectContaining({
      id: 'import',
      fingerprint: prepared.identity.fingerprint,
      scoringProfile: 'Two Flex Too Furious'
    }))
  })

  it('restores importIdentity and imported pool association on hydrate', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const prepared = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    if (!prepared.ok) throw new Error('league A failed')

    playersTable.toArray.mockResolvedValue(prepared.players)
    importMetaTable.get.mockResolvedValue({
      id: 'import',
      fingerprint: prepared.identity.fingerprint,
      season: prepared.identity.season,
      asOfDate: prepared.identity.asOfDate,
      rankingType: prepared.identity.rankingType,
      scoringProfile: prepared.identity.scoringProfile,
      leagueSize: prepared.identity.leagueSize,
      sourceCheatsheetId: prepared.identity.sourceCheatsheetId,
      sourceUrl: prepared.identity.sourceUrl,
      importedAt: Date.now(),
      playerCount: prepared.players.length,
      positionCounts: prepared.identity.positionCounts,
      savedProfileId: 'profile-a',
      savedProfileName: 'Two Flex Too Furious'
    })

    useDraftStore.setState({ importIdentity: undefined, players: [], hydrated: false, activeSavedProfileId: undefined })
    await useDraftStore.getState().hydrate()

    const { importIdentity, players } = useDraftStore.getState()
    expect(importIdentity?.scoringProfile).toBe('Two Flex Too Furious')
    expect(importIdentity?.fingerprint).toBe(prepared.identity.fingerprint)
    expect(players).toEqual(prepared.players)
    expect(players.every((player) => player.importSource?.fingerprint === importIdentity?.fingerprint)).toBe(true)
  })

  it('clears importIdentity after loadBundledRankings restores bundled pool', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { seedPlayers } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    const prepared = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    if (!prepared.ok) throw new Error('league A failed')
    await useDraftStore.getState().commitFootballersImport(prepared)
    expect(useDraftStore.getState().importIdentity?.scoringProfile).toBe('Two Flex Too Furious')

    await useDraftStore.getState().loadBundledRankings()

    expect(useDraftStore.getState().importIdentity).toBeUndefined()
    expect(useDraftStore.getState().activeSavedProfileId).toBeUndefined()
    expect(useDraftStore.getState().players).toEqual(seedPlayers)
    expect(importMetaTable.delete).toHaveBeenCalledWith('import')
  })

  it('clears importIdentity after resetDraft restores bundled pool', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { seedPlayers } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    const prepared = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    if (!prepared.ok) throw new Error('league A failed')
    await useDraftStore.getState().commitFootballersImport(prepared)
    expect(useDraftStore.getState().importIdentity?.scoringProfile).toBe('Two Flex Too Furious')

    await useDraftStore.getState().resetDraft()

    expect(useDraftStore.getState().importIdentity).toBeUndefined()
    expect(useDraftStore.getState().activeSavedProfileId).toBeUndefined()
    expect(useDraftStore.getState().players).toEqual(seedPlayers)
    expect(importMetaTable.delete).toHaveBeenCalledWith('import')
  })
})

describe('saved Footballers rankings profiles', () => {
  const storedProfiles: Array<{
    id: string
    displayName: string
    normalizedName: string
    dataset: import('../data/footballersImport').FootballersRankingDataset
    createdAt: number
    updatedAt: number
  }> = []

  beforeEach(async () => {
    storedProfiles.length = 0
    vi.clearAllMocks()
    adjustmentsTable.toArray.mockResolvedValue([])
    settingsTable.get.mockResolvedValue(undefined)
    metaTable.get.mockImplementation(async (id: string) => (id === 'seed' ? { id: 'seed', version: '2026.6' } : undefined))
    importMetaTable.get.mockResolvedValue(undefined)
    savedRankingsTable.put.mockImplementation(async (profile: typeof storedProfiles[number]) => {
      const index = storedProfiles.findIndex((item) => item.id === profile.id)
      if (index >= 0) storedProfiles[index] = profile
      else storedProfiles.push(profile)
    })
    savedRankingsTable.get.mockImplementation(async (id: string) => storedProfiles.find((item) => item.id === id))
    savedRankingsTable.orderBy.mockReturnValue({
      reverse: vi.fn(() => ({
        toArray: vi.fn(async () => [...storedProfiles].sort((a, b) => b.updatedAt - a.updatedAt))
      }))
    })
    evaluationRecordsTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    picksTable.orderBy.mockReturnValue({ toArray: vi.fn().mockResolvedValue([]) })
    const { defaultLeague } = await import('../types')
    const { useDraftStore } = await import('./draftStore')
    useDraftStore.setState({
      players: [],
      adjustments: {},
      picks: [],
      keepers: [],
      settings: {
        ...defaultLeague,
        teamCount: 8,
        rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 2, SUPERFLEX: 0, BENCH: 6, K: 0, DST: 1 }
      },
      recommendations: [],
      recommendationContext: undefined,
      evaluationRecords: [],
      hydrated: true,
      importIdentity: undefined,
      savedRankings: [],
      activeSavedProfileId: undefined
    })
  })

  it('saves imported CSV, resets to bundled, and reactivates with identical CSV-owned fields', async () => {
    const { buildFootballersCsv, leagueARows } = await import('../data/footballersImport.fixtures')
    const { seedPlayers } = await import('../data/seed')
    const { useDraftStore } = await import('./draftStore')
    const prepared = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    if (!prepared.ok) throw new Error('league A failed')
    await useDraftStore.getState().commitFootballersImport(prepared, { profileName: 'League A' })
    const active = useDraftStore.getState()
    const joshBeforeReset = active.players.find((player) => player.id === 'josh-allen-buf-qb')
    expect(active.savedRankings).toHaveLength(1)
    expect(active.activeSavedProfileId).toBeTruthy()

    await useDraftStore.getState().resetDraft()
    expect(useDraftStore.getState().players).toEqual(seedPlayers)
    expect(useDraftStore.getState().importIdentity).toBeUndefined()

    const profileId = active.savedRankings[0]!.id
    await useDraftStore.getState().saveLeagueSetup(useDraftStore.getState().settings, profileId)
    const joshAfter = useDraftStore.getState().players.find((player) => player.id === 'josh-allen-buf-qb')
    expect(joshAfter?.tier).toBe(joshBeforeReset?.tier)
    expect(joshAfter?.adp).toBe(joshBeforeReset?.adp)
    expect(joshAfter?.projectedPoints).toBe(joshBeforeReset?.projectedPoints)
    expect(useDraftStore.getState().importIdentity?.savedProfileName).toBe('League A')
  })

  it('switches saved A to saved B without leaving stale A metadata', async () => {
    const { buildFootballersCsv, leagueARows, leagueBRows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    const leagueB = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' })
    )
    if (!leagueA.ok || !leagueB.ok) throw new Error('prepare failed')
    await useDraftStore.getState().commitFootballersImport(leagueA, { profileName: 'League A' })
    storedProfiles.push({
      id: 'profile-b',
      displayName: 'League B',
      normalizedName: 'league b',
      dataset: leagueB.dataset,
      createdAt: 1,
      updatedAt: 2
    })
    useDraftStore.setState({
      savedRankings: [
        ...useDraftStore.getState().savedRankings,
        {
          id: 'profile-b',
          displayName: 'League B',
          fingerprint: leagueB.identity.fingerprint,
          scoringProfile: leagueB.identity.scoringProfile,
          leagueSize: leagueB.identity.leagueSize,
          asOfDate: leagueB.identity.asOfDate,
          playerCount: leagueB.players.length,
          updatedAt: 2
        }
      ]
    })
    await useDraftStore.getState().saveLeagueSetup(useDraftStore.getState().settings, 'profile-b')
    const josh = useDraftStore.getState().players.find((player) => player.id === 'josh-allen-buf-qb')
    expect(josh?.tier).toBe(2)
    expect(josh?.adp).toBe(802)
    expect(useDraftStore.getState().importIdentity?.fingerprint).toBe(leagueB.identity.fingerprint)
  })

  it('fails saved B activation when a keeper references a missing player and keeps saved A active', async () => {
    const { buildFootballersCsv, leagueARows, leagueBRows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    const leagueB = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' })
    )
    if (!leagueA.ok || !leagueB.ok) throw new Error('prepare failed')
    await useDraftStore.getState().commitFootballersImport(leagueA, { profileName: 'League A' })
    const before = useDraftStore.getState()
    useDraftStore.setState({
      keepers: [{
        id: 'keeper-1',
        teamId: 1,
        playerId: 'missing-player-id',
        playerName: 'Missing Player',
        position: 'RB',
        roundCost: 1,
        timestamp: 1
      }]
    })
    storedProfiles.push({
      id: 'profile-b',
      displayName: 'League B',
      normalizedName: 'league b',
      dataset: leagueB.dataset,
      createdAt: 1,
      updatedAt: 2
    })
    await expect(useDraftStore.getState().saveLeagueSetup(before.settings, 'profile-b')).rejects.toThrow(/Keeper Missing Player/)
    const after = useDraftStore.getState()
    expect(after.importIdentity?.fingerprint).toBe(before.importIdentity?.fingerprint)
    expect(after.players).toEqual(before.players)
    expect(after.settings).toEqual(before.settings)
  })

  it('keeps settings A and rankings A active when staged settings B and rankings B fail together', async () => {
    const { buildFootballersCsv, leagueARows, leagueBRows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    const leagueB = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' })
    )
    if (!leagueA.ok || !leagueB.ok) throw new Error('prepare failed')
    await useDraftStore.getState().commitFootballersImport(leagueA, { profileName: 'League A' })
    const before = useDraftStore.getState()
    const settingsB = {
      ...before.settings,
      teamCount: 10,
      userTeam: 5
    }
    storedProfiles.push({
      id: 'profile-b',
      displayName: 'League B',
      normalizedName: 'league b',
      dataset: leagueB.dataset,
      createdAt: 1,
      updatedAt: 2
    })
    await expect(useDraftStore.getState().saveLeagueSetup(settingsB, 'profile-b')).rejects.toThrow(/league size/)
    const after = useDraftStore.getState()
    expect(after.settings).toEqual(before.settings)
    expect(after.importIdentity?.fingerprint).toBe(before.importIdentity?.fingerprint)
    expect(after.players).toEqual(before.players)
    expect(settingsTable.put).not.toHaveBeenCalled()
  })

  it('activates staged settings B and rankings B together on successful Save League', async () => {
    const { buildFootballersCsv, leagueARows, leagueBRows } = await import('../data/footballersImport.fixtures')
    const { useDraftStore } = await import('./draftStore')
    const leagueA = useDraftStore.getState().prepareFootballersImport(buildFootballersCsv(leagueARows()))
    const leagueB = useDraftStore.getState().prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' })
    )
    if (!leagueA.ok || !leagueB.ok) throw new Error('prepare failed')
    await useDraftStore.getState().commitFootballersImport(leagueA, { profileName: 'League A' })
    const settingsB = {
      ...useDraftStore.getState().settings,
      name: 'Sunday B',
      userTeam: 3
    }
    storedProfiles.push({
      id: 'profile-b',
      displayName: 'League B',
      normalizedName: 'league b',
      dataset: leagueB.dataset,
      createdAt: 1,
      updatedAt: 2
    })
    await useDraftStore.getState().saveLeagueSetup(settingsB, 'profile-b')
    const after = useDraftStore.getState()
    expect(after.settings.name).toBe('Sunday B')
    expect(after.settings.userTeam).toBe(3)
    expect(after.importIdentity?.fingerprint).toBe(leagueB.identity.fingerprint)
    expect(after.players.find((player) => player.id === 'josh-allen-buf-qb')?.tier).toBe(2)
    expect(settingsTable.put).toHaveBeenCalled()
  })
})
