import type { Player } from '../types'
import bundle from './expertRankings.json'

export const SEED_VERSION = bundle.seedVersion

type SeedRow = (typeof bundle.players)[number]

function optionalAdp(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined
}

function toSeedPlayer(player: SeedRow): Player {
  return {
    id: player.id,
    name: player.name,
    position: player.position as Player['position'],
    team: player.team,
    projectedPoints: player.projectedPoints,
    adp: player.adp,
    espnAdp: optionalAdp('espnAdp' in player ? player.espnAdp : undefined),
    sleeperAdp: optionalAdp('sleeperAdp' in player ? player.sleeperAdp : undefined),
    tier: player.tier,
    depthChartRank: typeof player.depthChartRank === 'number' ? player.depthChartRank : undefined,
    depthChartSource: typeof player.depthChartSource === 'string' ? player.depthChartSource : undefined,
    upsideScore: typeof player.upsideScore === 'number' ? player.upsideScore : undefined,
    riskScore: typeof player.riskScore === 'number' ? player.riskScore : undefined,
    isRookie: player.isRookie === true,
    isBreakout: player.isBreakout === true,
    byeWeek: typeof player.byeWeek === 'number' ? player.byeWeek : undefined,
    irEligible: 'irEligible' in player && player.irEligible === true,
    injuryStatus: 'injuryStatus' in player && typeof player.injuryStatus === 'string'
      ? player.injuryStatus
      : undefined,
    expectedReturnWeek: 'expectedReturnWeek' in player && typeof player.expectedReturnWeek === 'number'
      ? player.expectedReturnWeek
      : undefined
  }
}

export const seedPlayers: Player[] = bundle.players.map(toSeedPlayer)

export function isLegacyDemoPool(players: Player[]): boolean {
  return players.length > 0 && players.length <= 30 && players.every((player) => player.id.startsWith('seed-'))
}

export function isCsvImportPool(players: Player[]): boolean {
  return players.some((player) => player.id.startsWith('csv-'))
}

export function shouldRefreshBundledAdp(stored: Player[]): boolean {
  if (!stored.length || isCsvImportPool(stored) || isLegacyDemoPool(stored)) return false
  const seedHasEspn = seedPlayers.some((player) => player.espnAdp != null)
  const storedHasEspn = stored.some((player) => player.espnAdp != null)
  return seedHasEspn && !storedHasEspn
}
