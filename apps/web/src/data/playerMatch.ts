import type { Player, PlayerPosition } from '../types'

export type MatchMethod = 'projectId' | 'slugPosition' | 'namePosition' | 'teamPosition'

export interface MatchWarning {
  row: number
  playerName: string
  message: string
}

export interface MatchResult {
  bundled: Player
  method: MatchMethod
  warnings: MatchWarning[]
}

const SUFFIX_PATTERN = /\b(jr\.?|sr\.?|ii|iii|iv|v)\b/gi

export function normalizeToken(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/['’.]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(SUFFIX_PATTERN, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function normalizePosition(raw: string): PlayerPosition | null {
  const value = raw.trim().toUpperCase()
  if (value === 'D/ST' || value === 'DEF') return 'DST'
  if (['QB', 'RB', 'WR', 'TE', 'K', 'DST'].includes(value)) return value as PlayerPosition
  return null
}

function projectIdFromParts(slug: string, team: string, position: PlayerPosition): string {
  return `${slug}-${team.toLowerCase()}-${position.toLowerCase()}`
}

function isProjectIdNamespace(id: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)+$/i.test(id) && !/^\d+$/.test(id)
}

export class BundledPlayerMatcher {
  private readonly byProjectId = new Map<string, Player>()
  private readonly bySlugPosition = new Map<string, Player[]>()
  private readonly byNamePosition = new Map<string, Player[]>()
  private readonly byTeamPosition = new Map<string, Player[]>()

  constructor(bundledPlayers: Player[]) {
    for (const player of bundledPlayers) {
      this.byProjectId.set(player.id, player)
      const slug = player.id.split('-').slice(0, -2).join('-')
      if (slug) {
        this.push(this.bySlugPosition, `${slug}:${player.position}`, player)
      }
      this.push(this.byNamePosition, `${normalizeToken(player.name)}:${player.position}`, player)
      this.push(this.byTeamPosition, `${player.team.toUpperCase()}:${player.position}`, player)
    }
  }

  match(input: {
    row: number
    name: string
    position: PlayerPosition
    team: string
    slug?: string
    importedId?: string
  }): { ok: true; result: MatchResult } | { ok: false; reason: string } {
    const warnings: MatchWarning[] = []
    const team = input.team.trim().toUpperCase() || 'FA'
    const slug = input.slug?.trim()

    if (input.importedId && isProjectIdNamespace(input.importedId)) {
      const bundled = this.byProjectId.get(input.importedId)
      if (bundled && bundled.position === input.position) {
        return { ok: true, result: { bundled, method: 'projectId', warnings } }
      }
    }

    if (slug) {
      const exactId = projectIdFromParts(slug, team, input.position)
      const bundled = this.byProjectId.get(exactId)
      if (bundled) {
        return { ok: true, result: { bundled, method: 'slugPosition', warnings } }
      }
      const slugMatches = this.bySlugPosition.get(`${slug}:${input.position}`) ?? []
      const uniqueSlug = this.pickUnique(slugMatches, team, input.name, warnings, input.row)
      if (uniqueSlug) {
        return { ok: true, result: { bundled: uniqueSlug, method: 'slugPosition', warnings } }
      }
      if (slugMatches.length > 1) {
        return { ok: false, reason: `ambiguous slug match for ${input.name}` }
      }
    }

    const nameKey = `${normalizeToken(input.name)}:${input.position}`
    const nameMatches = this.byNamePosition.get(nameKey) ?? []
    const uniqueName = this.pickUnique(nameMatches, team, input.name, warnings, input.row)
    if (uniqueName) {
      return { ok: true, result: { bundled: uniqueName, method: 'namePosition', warnings } }
    }
    if (nameMatches.length > 1) {
      return { ok: false, reason: `ambiguous name match for ${input.name}` }
    }

    const teamMatches = this.byTeamPosition.get(`${team}:${input.position}`) ?? []
    if (input.position === 'DST' && teamMatches.length === 1) {
      return { ok: true, result: { bundled: teamMatches[0], method: 'teamPosition', warnings } }
    }

    return { ok: false, reason: `no bundled projection match for ${input.name}` }
  }

  private push(map: Map<string, Player[]>, key: string, player: Player) {
    const bucket = map.get(key) ?? []
    bucket.push(player)
    map.set(key, bucket)
  }

  private pickUnique(
    candidates: Player[],
    team: string,
    name: string,
    warnings: MatchWarning[],
    row: number
  ): Player | undefined {
    if (candidates.length === 1) {
      const candidate = candidates[0]
      if (candidate.team.toUpperCase() !== team) {
        warnings.push({
          row,
          playerName: name,
          message: `team changed from ${candidate.team} to ${team}; matched by identity`
        })
      }
      return candidate
    }
    if (candidates.length > 1) {
      const teamMatches = candidates.filter((candidate) => candidate.team.toUpperCase() === team)
      if (teamMatches.length === 1) {
        return teamMatches[0]
      }
    }
    return undefined
  }
}
