import { create } from 'zustand'
import { db, queueEvent } from '../data/db'
import { SEED_VERSION, isCsvImportPool, isLegacyDemoPool, seedPlayers, shouldRefreshBundledAdp } from '../data/seed'
import type {
  DraftEvaluationRecord,
  DraftPick,
  EngineMode,
  EvaluationRecommendation,
  KeeperAssignment,
  LeagueSettings,
  Player,
  Recommendation,
  RecommendationGenerationContext,
  ScoreBreakdown,
  UserAdjustment
} from '../types'
import { defaultLeague } from '../types'
import { getRecommendations, prepareOfflineEngine } from '../engine/adapter'

interface DraftStore {
  players: Player[]
  adjustments: Record<string, UserAdjustment>
  picks: DraftPick[]
  keepers: KeeperAssignment[]
  settings: LeagueSettings
  recommendations: Recommendation[]
  recommendationContext?: RecommendationGenerationContext
  evaluationRecords: DraftEvaluationRecord[]
  engineMode: EngineMode
  engineWarning?: string
  offlineReady: boolean
  hydrated: boolean
  hydrate: () => Promise<void>
  importPlayers: (players: Player[]) => Promise<void>
  loadBundledRankings: () => Promise<void>
  draftPlayer: (player: Player) => Promise<void>
  assignKeeper: (player: Player, teamId: number) => Promise<void>
  removeKeeper: (id: string) => Promise<void>
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

export function roundForPick(pickNumber: number, teamCount: number) {
  return Math.floor((pickNumber - 1) / teamCount) + 1
}

export function rosterForTeam(picks: DraftPick[], team: number, teamCount: number) {
  return picks
    .filter((pick) => teamForPick(pick.pickNumber, teamCount) === team)
    .sort((a, b) => a.pickNumber - b.pickNumber)
}

export function keeperToPick(keeper: KeeperAssignment): DraftPick {
  return {
    id: keeper.id,
    pickNumber: 0,
    teamId: keeper.teamId,
    playerId: keeper.playerId,
    playerName: keeper.playerName,
    position: keeper.position,
    timestamp: keeper.timestamp,
    isKeeper: true
  }
}

export function rosterEntriesForTeam(
  picks: DraftPick[],
  keepers: KeeperAssignment[],
  team: number,
  teamCount: number
) {
  const teamKeepers = keepers.filter((keeper) => keeper.teamId === team).map(keeperToPick)
  return [...teamKeepers, ...rosterForTeam(picks, team, teamCount)]
}

export function keptPlayerIds(keepers: KeeperAssignment[]) {
  return new Set(keepers.map((keeper) => keeper.playerId))
}

export function unavailablePlayerIds(picks: DraftPick[], keepers: KeeperAssignment[]) {
  const ids = keptPlayerIds(keepers)
  for (const pick of picks) ids.add(pick.playerId)
  return ids
}

function copyPlayer(player: Player): Player {
  return { ...player }
}

function copySettings(settings: LeagueSettings): LeagueSettings {
  return { ...settings, rosterSlots: { ...settings.rosterSlots } }
}

function exportRecommendation(
  recommendation: Recommendation,
  rank: number,
  playersById: Map<string, Player>
): EvaluationRecommendation | undefined {
  const player = playersById.get(recommendation.playerId)
  if (!player) return undefined
  return {
    rank,
    player: copyPlayer(player),
    dvsScore: recommendation.dvsScore,
    decisionScore: recommendation.breakdown.decisionScore ?? recommendation.dvsScore,
    tierLabel: recommendation.tierLabel,
    breakdown: { ...recommendation.breakdown },
    reasonStrings: [...(recommendation.reasons ?? (recommendation.explanation ? [recommendation.explanation] : []))]
  }
}

function selectionEngineFields(
  playerId: string,
  recommendations: Recommendation[]
): {
  rank: number | null
  decisionScore: number | null
  breakdown: ScoreBreakdown | null
} {
  const index = recommendations.findIndex((item) => item.playerId === playerId)
  const recommendation = index >= 0 ? recommendations[index] : undefined
  return {
    rank: index >= 0 && index < 10 ? index + 1 : null,
    decisionScore: recommendation
      ? recommendation.breakdown.decisionScore ?? recommendation.dvsScore
      : null,
    breakdown: recommendation ? { ...recommendation.breakdown } : null
  }
}

export function createDraftEvaluationRecord(
  state: Pick<
    DraftStore,
    'players' | 'adjustments' | 'picks' | 'keepers' | 'settings' | 'recommendations'
    | 'recommendationContext' | 'engineMode' | 'engineWarning'
  >,
  pick: DraftPick,
  selectedPlayer: Player
): DraftEvaluationRecord {
  const capturedAt = Date.now()
  const playersById = new Map(state.players.map((player) => [player.id, player]))
  const unavailable = unavailablePlayerIds(state.picks, state.keepers)
  const generatedForPickIds = state.recommendationContext?.generatedForPickIds ?? []
  const recommendationsMatchBoardState = Boolean(state.recommendationContext)
    && generatedForPickIds.length === state.picks.length
    && generatedForPickIds.every((id, index) => id === state.picks[index]?.id)
  const selectedFields = selectionEngineFields(selectedPlayer.id, state.recommendations)
  const topRecommendations = state.recommendations.slice(0, 10).flatMap((recommendation, index) => {
    const exported = exportRecommendation(recommendation, index + 1, playersById)
    return exported ? [exported] : []
  })
  const recommendationGeneration: RecommendationGenerationContext = state.recommendationContext ?? {
    formulaVersion: state.settings.formulaVersion ?? null,
    oneTurnSims: null,
    simulationSeed: null,
    formulaParams: null,
    engineMode: state.engineMode,
    engineWarning: state.engineWarning,
    generatedAt: capturedAt,
    generatedForPickIds: [],
    generatedForPickCount: 0
  }

  return {
    id: crypto.randomUUID(),
    pickId: pick.id,
    pickNumber: pick.pickNumber,
    round: roundForPick(pick.pickNumber, state.settings.teamCount),
    capturedAt,
    status: 'active',
    userRoster: rosterEntriesForTeam(
      state.picks,
      state.keepers,
      state.settings.userTeam,
      state.settings.teamCount
    ).map((entry) => ({ ...entry })),
    availablePlayerPool: state.players.filter((player) => !unavailable.has(player.id)).map(copyPlayer),
    topRecommendations,
    recommendationGeneration: {
      ...recommendationGeneration,
      formulaParams: recommendationGeneration.formulaParams
        ? { ...recommendationGeneration.formulaParams }
        : null,
      generatedForPickIds: [...recommendationGeneration.generatedForPickIds]
    },
    recommendationsMatchBoardState,
    actualSelection: copyPlayer(selectedPlayer),
    actualSelectionRecommendationRank: selectedFields.rank,
    actualSelectionDecisionScore: selectedFields.decisionScore,
    actualSelectionScoreBreakdown: selectedFields.breakdown,
    boardState: {
      settings: copySettings(state.settings),
      picks: state.picks.map((existingPick) => ({ ...existingPick })),
      keepers: state.keepers.map((keeper) => ({ ...keeper })),
      adjustments: Object.values(state.adjustments).map((adjustment) => ({ ...adjustment })),
      players: state.players.map(copyPlayer)
    },
    revisions: []
  }
}

let draftWriteChain = Promise.resolve()

function enqueueDraftWrite<T>(work: () => Promise<T>): Promise<T> {
  const run = draftWriteChain.then(work, work)
  draftWriteChain = run.then(() => undefined, () => undefined)
  return run
}

let recommendationRequestId = 0

export const useDraftStore = create<DraftStore>((set, get) => ({
  players: [],
  adjustments: {},
  picks: [],
  keepers: [],
  settings: defaultLeague,
  recommendations: [],
  evaluationRecords: [],
  engineMode: 'development-fallback',
  offlineReady: false,
  hydrated: false,
  hydrate: async () => {
    const [storedPlayers, storedAdjustments, picks, keepers, storedSettings, storedMeta, evaluationRecords] = await Promise.all([
      db.players.toArray(),
      db.adjustments.toArray(),
      db.picks.orderBy('pickNumber').toArray(),
      db.keepers.toArray(),
      db.settings.get('active'),
      db.meta.get('seed'),
      db.evaluationRecords.orderBy('capturedAt').toArray()
    ])
    const seedChanged = storedMeta?.version !== SEED_VERSION
    const shouldLoadBundle = !storedPlayers.length
      || isLegacyDemoPool(storedPlayers)
      || shouldRefreshBundledAdp(storedPlayers)
      || (seedChanged && !isCsvImportPool(storedPlayers))
    const players = shouldLoadBundle ? seedPlayers : storedPlayers
    if (shouldLoadBundle) {
      await db.transaction('rw', db.players, db.meta, async () => {
        if (storedPlayers.length) await db.players.clear()
        await db.players.bulkPut(players)
        await db.meta.put({ id: 'seed', version: SEED_VERSION })
      })
    }
    set({
      players,
      adjustments: Object.fromEntries(storedAdjustments.map((item) => [item.playerId, item])),
      picks,
      keepers,
      settings: storedSettings ? { ...storedSettings, id: undefined } as unknown as LeagueSettings : defaultLeague,
      evaluationRecords,
      hydrated: true
    })
    await get().refreshRecommendations()
    try {
      await prepareOfflineEngine()
      set({ offlineReady: true })
      await get().refreshRecommendations()
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
  loadBundledRankings: async () => {
    await get().importPlayers(seedPlayers)
    await db.meta.put({ id: 'seed', version: SEED_VERSION })
  },
  draftPlayer: async (player) => enqueueDraftWrite(async () => {
    const state = get()
    if (state.picks.some((pick) => pick.playerId === player.id)) return
    if (state.keepers.some((keeper) => keeper.playerId === player.id)) return
    const rosterSize = Object.values(state.settings.rosterSlots).reduce((sum, count) => sum + count, 0)
    const liveRounds = rosterSize - (state.settings.keeperSlots ?? 0)
    if (state.picks.length >= state.settings.teamCount * liveRounds) return
    const pickNumber = state.picks.length + 1
    const pick: DraftPick = {
      id: crypto.randomUUID(),
      pickNumber,
      teamId: teamForPick(pickNumber, state.settings.teamCount),
      playerId: player.id,
      playerName: player.name,
      position: player.position,
      timestamp: Date.now()
    }
    const evaluation = pick.teamId === state.settings.userTeam
      ? createDraftEvaluationRecord(state, pick, player)
      : undefined
    await db.transaction('rw', db.picks, db.evaluationRecords, db.events, async () => {
      await db.picks.put(pick)
      if (evaluation) await db.evaluationRecords.put(evaluation)
      await queueEvent('PICK_CREATED', pick)
    })
    set((current) => ({
      picks: [...current.picks, pick],
      evaluationRecords: evaluation
        ? [...current.evaluationRecords, evaluation]
        : current.evaluationRecords
    }))
    await get().refreshRecommendations()
  }),
  assignKeeper: async (player, teamId) => enqueueDraftWrite(async () => {
    const { settings, picks, keepers } = get()
    if (teamId < 1 || teamId > settings.teamCount) return
    if (picks.some((pick) => pick.playerId === player.id)) return
    if (keepers.some((keeper) => keeper.playerId === player.id)) return
    const keeper: KeeperAssignment = {
      id: crypto.randomUUID(),
      teamId,
      playerId: player.id,
      playerName: player.name,
      position: player.position,
      roundCost: 1,
      timestamp: Date.now()
    }
    await db.keepers.put(keeper)
    await queueEvent('KEEPER_ASSIGNED', keeper)
    set((state) => ({ keepers: [...state.keepers, keeper] }))
    await get().refreshRecommendations()
  }),
  removeKeeper: async (id) => enqueueDraftWrite(async () => {
    const removed = get().keepers.find((keeper) => keeper.id === id)
    if (!removed) return
    await db.keepers.delete(id)
    await queueEvent('KEEPER_REMOVED', removed)
    set((state) => ({ keepers: state.keepers.filter((keeper) => keeper.id !== id) }))
    await get().refreshRecommendations()
  }),
  correctPick: async (id, player) => enqueueDraftWrite(async () => {
    const current = get().picks.find((pick) => pick.id === id)
    if (!current || get().keepers.some((keeper) => keeper.playerId === player.id)) return
    if (get().picks.some((pick) => pick.id !== id && pick.playerId === player.id)) return
    const corrected: DraftPick = {
      ...current,
      playerId: player.id,
      playerName: player.name,
      position: player.position,
      timestamp: Date.now()
    }
    const existingEvaluation = get().evaluationRecords.find((record) => record.pickId === id && record.status === 'active')
    const evaluation = existingEvaluation
      ? (() => {
          const exportedRecommendation = existingEvaluation.topRecommendations.find(
            (recommendation) => recommendation.player.id === player.id
          )
          return {
            ...existingEvaluation,
            actualSelection: copyPlayer(player),
            actualSelectionRecommendationRank: exportedRecommendation?.rank ?? null,
            actualSelectionDecisionScore: exportedRecommendation?.decisionScore ?? null,
            actualSelectionScoreBreakdown: exportedRecommendation
              ? { ...exportedRecommendation.breakdown }
              : null,
            revisions: [
              ...existingEvaluation.revisions,
              {
                type: 'CORRECTED' as const,
                timestamp: corrected.timestamp,
                previousSelection: copyPlayer(existingEvaluation.actualSelection),
                nextSelection: copyPlayer(player)
              }
            ]
          }
        })()
      : undefined
    await db.transaction('rw', db.picks, db.evaluationRecords, db.events, async () => {
      await db.picks.put(corrected)
      if (evaluation) await db.evaluationRecords.put(evaluation)
      await queueEvent('PICK_CORRECTED', { before: current, after: corrected })
    })
    set((state) => ({
      picks: state.picks.map((pick) => pick.id === id ? corrected : pick),
      evaluationRecords: evaluation
        ? state.evaluationRecords.map((record) => record.id === evaluation.id ? evaluation : record)
        : state.evaluationRecords
    }))
    await get().refreshRecommendations()
  }),
  undoLastPick: async () => enqueueDraftWrite(async () => {
    const last = get().picks.at(-1)
    if (!last) return
    const existingEvaluation = get().evaluationRecords.find((record) => record.pickId === last.id && record.status === 'active')
    const evaluation = existingEvaluation
      ? {
          ...existingEvaluation,
          status: 'undone' as const,
          revisions: [
            ...existingEvaluation.revisions,
            {
              type: 'UNDONE' as const,
              timestamp: Date.now(),
              previousSelection: copyPlayer(existingEvaluation.actualSelection)
            }
          ]
        }
      : undefined
    await db.transaction('rw', db.picks, db.evaluationRecords, db.events, async () => {
      await db.picks.delete(last.id)
      if (evaluation) await db.evaluationRecords.put(evaluation)
      await queueEvent('PICK_UNDONE', last)
    })
    set((state) => ({
      picks: state.picks.slice(0, -1),
      evaluationRecords: evaluation
        ? state.evaluationRecords.map((record) => record.id === evaluation.id ? evaluation : record)
        : state.evaluationRecords
    }))
    await get().refreshRecommendations()
  }),
  removePick: async (id) => enqueueDraftWrite(async () => {
    const removed = get().picks.find((pick) => pick.id === id)
    const remaining = get().picks.filter((pick) => pick.id !== id).map((pick, index) => ({
      ...pick,
      pickNumber: index + 1,
      teamId: teamForPick(index + 1, get().settings.teamCount)
    }))
    const existingEvaluation = get().evaluationRecords.find((record) => record.pickId === id && record.status === 'active')
    const evaluation = existingEvaluation
      ? {
          ...existingEvaluation,
          status: 'removed' as const,
          revisions: [
            ...existingEvaluation.revisions,
            {
              type: 'REMOVED' as const,
              timestamp: Date.now(),
              previousSelection: copyPlayer(existingEvaluation.actualSelection)
            }
          ]
        }
      : undefined
    await db.transaction('rw', db.picks, db.evaluationRecords, db.events, async () => {
      await db.picks.clear()
      await db.picks.bulkPut(remaining)
      if (evaluation) await db.evaluationRecords.put(evaluation)
      if (removed) await queueEvent('PICK_REMOVED', removed)
    })
    set((state) => ({
      picks: remaining,
      evaluationRecords: evaluation
        ? state.evaluationRecords.map((record) => record.id === evaluation.id ? evaluation : record)
        : state.evaluationRecords
    }))
    await get().refreshRecommendations()
  }),
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
    const validKeepers = get().keepers.filter((keeper) => keeper.teamId >= 1 && keeper.teamId <= settings.teamCount)
    if (validKeepers.length !== get().keepers.length) {
      await db.transaction('rw', db.keepers, async () => {
        await db.keepers.clear()
        await db.keepers.bulkPut(validKeepers)
      })
    }
    await db.settings.put({ ...settings, id: 'active' })
    await queueEvent('SETTINGS_UPDATED', patch)
    set({ settings, keepers: validKeepers })
    await get().refreshRecommendations()
  },
  refreshRecommendations: async () => {
    const { players, adjustments, picks, keepers, settings } = get()
    if (!players.length) return
    const requestId = ++recommendationRequestId
    const generatedAt = Date.now()
    const generatedForPickIds = picks.map((pick) => pick.id)
    const unavailable = unavailablePlayerIds(picks, keepers)
    const result = await getRecommendations({ players, adjustments: Object.values(adjustments), picks, keepers, settings })
    if (requestId !== recommendationRequestId) return
    const recommendations = result.recommendations.filter((item) => !unavailable.has(item.playerId))
    set({
      recommendations,
      recommendationContext: {
        ...(result.configuration ?? {
          formulaVersion: settings.formulaVersion ?? null,
          oneTurnSims: null,
          simulationSeed: null,
          formulaParams: null
        }),
        engineMode: result.mode,
        engineWarning: result.warning,
        generatedAt,
        generatedForPickIds,
        generatedForPickCount: picks.length
      },
      engineMode: result.mode,
      engineWarning: result.warning
    })
  }
}))
