import type { Player } from '../types'
import bundle from './expertRankings.json'

export const SEED_VERSION = bundle.seedVersion

export const seedPlayers: Player[] = bundle.players.map((player) => ({
  id: player.id,
  name: player.name,
  position: player.position as Player['position'],
  team: player.team,
  projectedPoints: player.projectedPoints,
  adp: player.adp,
  tier: player.tier
}))

export function isLegacyDemoPool(players: Player[]): boolean {
  return players.length > 0 && players.length <= 30 && players.every((player) => player.id.startsWith('seed-'))
}
