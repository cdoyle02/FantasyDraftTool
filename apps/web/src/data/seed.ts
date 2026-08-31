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
    tier: player.tier
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
