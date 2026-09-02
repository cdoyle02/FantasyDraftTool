import Papa from 'papaparse'
import type {
  FootballersSourceTags,
  KeeperAssignment,
  LeagueSettings,
  Player,
  PlayerPosition,
  UserAdjustment
} from '../types'
import { seedPlayers } from './seed'
import { BundledPlayerMatcher, normalizePosition, type MatchWarning } from './playerMatch'

type CsvRow = Record<string, string>

const REQUIRED_HEADERS = [
  'season',
  'as_of_date',
  'ranking_type',
  'scoring_profile',
  'league_size',
  'position',
  'position_rank',
  'player_name',
  'source_cheatsheet_id'
] as const

const TAG_FIELDS = [
  ['my_guy', 'is_my_guy'],
  ['value', 'is_value'],
  ['bust', 'is_bust'],
  ['sleeper', 'is_sleeper'],
  ['rookie', 'is_rookie'],
  ['injured', 'is_injury_concern'],
  ['breakout', 'is_breakout']
] as const

const SKILL_POSITIONS = new Set<PlayerPosition>(['QB', 'RB', 'WR', 'TE'])

export interface ImportSourceIdentity {
  fingerprint: string
  season: number
  asOfDate: string
  rankingType: string
  scoringProfile: string
  leagueSize: number
  sourceCheatsheetId: string
  sourceUrl?: string
  positionCounts: Record<string, number>
}

export interface ImportPrepareWarning {
  row?: number
  message: string
}

export interface ImportPrepareError {
  row?: number
  field?: string
  message: string
}

export interface ImportPrepareSuccess {
  ok: true
  players: Player[]
  identity: ImportSourceIdentity
  warnings: ImportPrepareWarning[]
  matchWarnings: MatchWarning[]
}

export interface ImportPrepareFailure {
  ok: false
  errors: ImportPrepareError[]
  warnings: ImportPrepareWarning[]
}

export type ImportPrepareResult = ImportPrepareSuccess | ImportPrepareFailure

export interface ImportCommitContext {
  settings: LeagueSettings
  picks: Array<{ playerId: string }>
  keepers: KeeperAssignment[]
  adjustments: Record<string, UserAdjustment>
}

function normalizeHeader(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_')
}

function rowValue(row: CsvRow, headerMap: Map<string, string>, field: string): string {
  const header = headerMap.get(field)
  return header ? (row[header] ?? '').trim() : ''
}

function optionalNumber(value: string, field: string, row: number): number | undefined {
  if (!value) return undefined
  const parsed = Number(value.replace(/,/g, ''))
  if (!Number.isFinite(parsed)) {
    throw new Error(`row ${row}: ${field} must be numeric when present`)
  }
  return parsed
}

function optionalInt(value: string, field: string, row: number): number | undefined {
  const parsed = optionalNumber(value, field, row)
  return parsed === undefined ? undefined : Math.trunc(parsed)
}

function parseBoolean(value: string): boolean {
  return value === '1' || value.toLowerCase() === 'true'
}

function parseTagsField(value: string): Set<string> {
  if (!value) return new Set()
  return new Set(value.split('|').map((item) => item.trim()).filter(Boolean))
}

function tagsFromBooleans(row: CsvRow, headerMap: Map<string, string>): FootballersSourceTags {
  const tags: FootballersSourceTags = {}
  for (const [tag, column] of TAG_FIELDS) {
    const raw = rowValue(row, headerMap, column)
    if (!raw) continue
    if (raw !== '0' && raw !== '1') {
      throw new Error(`${column} must be 0 or 1`)
    }
    const enabled = parseBoolean(raw)
    if (tag === 'my_guy') tags.myGuy = enabled
    if (tag === 'value') tags.value = enabled
    if (tag === 'bust') tags.bust = enabled
    if (tag === 'sleeper') tags.sleeper = enabled
    if (tag === 'rookie') tags.rookie = enabled
    if (tag === 'injured') tags.injured = enabled
    if (tag === 'breakout') tags.breakout = enabled
  }
  return tags
}

function tagSetFromRecord(tags: FootballersSourceTags): Set<string> {
  const result = new Set<string>()
  if (tags.myGuy) result.add('my_guy')
  if (tags.value) result.add('value')
  if (tags.bust) result.add('bust')
  if (tags.sleeper) result.add('sleeper')
  if (tags.rookie) result.add('rookie')
  if (tags.injured) result.add('injured')
  if (tags.breakout) result.add('breakout')
  return result
}

function looksLikeFormula(value: string): boolean {
  return /^[=+\-@]/.test(value)
}

function fingerprintForSheet(
  identity: {
    sourceCheatsheetId: string
    season: number
    leagueSize: number
    scoringProfile: string
  },
  rows: Array<{ position: string; positionRank: number; name: string }>
): string {
  const signature = rows
    .map((row) => `${row.position}:${row.positionRank}:${row.name}`)
    .sort()
    .join('|')
  const raw = [
    identity.sourceCheatsheetId,
    identity.season,
    identity.leagueSize,
    identity.scoringProfile,
    signature
  ].join('::')
  let hash = 0
  for (let index = 0; index < raw.length; index += 1) {
    hash = ((hash << 5) - hash + raw.charCodeAt(index)) | 0
  }
  return `tff-${Math.abs(hash).toString(36)}`
}

function buildPlayer(
  bundled: Player,
  csv: {
    name: string
    team: string
    position: PlayerPosition
    positionRank: number
    tier?: number
    tierRank?: number
    tierSize?: number
    tierValueMultiplier?: number
    adp?: number
    adpRoundPick?: string
    riskScore?: number
    upsideScore?: number
    byeWeek?: number
    slug?: string
    sourceTags: FootballersSourceTags
    tags?: string
    identity: ImportSourceIdentity
  }
): Player {
  return {
    id: bundled.id,
    name: csv.name,
    position: csv.position,
    team: csv.team,
    projectedPoints: bundled.projectedPoints,
    adp: csv.adp,
    espnAdp: bundled.espnAdp,
    sleeperAdp: bundled.sleeperAdp,
    tier: csv.tier ?? 1,
    depthChartRank: bundled.depthChartRank,
    depthChartSource: bundled.depthChartSource,
    upsideScore: csv.upsideScore,
    riskScore: csv.riskScore,
    isRookie: csv.sourceTags.rookie ?? false,
    isBreakout: csv.sourceTags.breakout ?? false,
    injuryStatus: csv.sourceTags.injured ? 'INJURY_CONCERN' : bundled.injuryStatus,
    irEligible: bundled.irEligible,
    expectedReturnWeek: bundled.expectedReturnWeek,
    byeWeek: csv.byeWeek,
    positionRank: csv.positionRank,
    tierRank: csv.tierRank,
    tierSize: csv.tierSize,
    tierValueMultiplier: csv.tierValueMultiplier,
    adpRoundPick: csv.adpRoundPick,
    playerSlug: csv.slug,
    sourceTags: csv.sourceTags,
    sourceTagsRaw: csv.tags,
    importSource: {
      season: csv.identity.season,
      asOfDate: csv.identity.asOfDate,
      rankingType: csv.identity.rankingType,
      scoringProfile: csv.identity.scoringProfile,
      leagueSize: csv.identity.leagueSize,
      sourceCheatsheetId: csv.identity.sourceCheatsheetId,
      sourceUrl: csv.identity.sourceUrl,
      fingerprint: csv.identity.fingerprint
    }
  }
}

function validateLeagueCompatibility(
  settings: LeagueSettings,
  identity: { leagueSize: number },
  positionCounts: Record<string, number>
): ImportPrepareError[] {
  const errors: ImportPrepareError[] = []
  if (identity.leagueSize !== settings.teamCount) {
    errors.push({
      field: 'league_size',
      message: `CSV league size ${identity.leagueSize} does not match League Setup team count ${settings.teamCount}.`
    })
  }
  const kRows = positionCounts.K ?? 0
  const dstRows = positionCounts.DST ?? 0
  const kSlots = settings.rosterSlots.K ?? 0
  const dstSlots = settings.rosterSlots.DST ?? 0
  if (kSlots === 0 && kRows > 0) {
    errors.push({ field: 'position', message: 'CSV includes kickers but League Setup has K = 0.' })
  }
  if (kSlots > 0 && kRows === 0) {
    errors.push({ field: 'position', message: 'League Setup requires kickers but CSV has no K rows.' })
  }
  if (dstSlots === 0 && dstRows > 0) {
    errors.push({ field: 'position', message: 'CSV includes defenses but League Setup has DST = 0.' })
  }
  if (dstSlots > 0 && dstRows === 0) {
    errors.push({ field: 'position', message: 'League Setup requires defenses but CSV has no DST rows.' })
  }
  return errors
}

function validateReferences(
  preparedIds: Set<string>,
  keepers: KeeperAssignment[],
  adjustments: Record<string, UserAdjustment>
): { errors: ImportPrepareError[]; warnings: ImportPrepareWarning[] } {
  const errors: ImportPrepareError[] = []
  const warnings: ImportPrepareWarning[] = []
  for (const keeper of keepers) {
    if (!preparedIds.has(keeper.playerId)) {
      errors.push({
        message: `Keeper ${keeper.playerName} (${keeper.playerId}) is not present in the imported pool.`
      })
    }
  }
  for (const adjustment of Object.values(adjustments)) {
    if (!preparedIds.has(adjustment.playerId)) {
      warnings.push({
        message: `Manual adjustment for ${adjustment.playerId} is not present in the imported pool.`
      })
    }
  }
  return { errors, warnings }
}

export function prepareFootballersImport(
  content: string,
  settings: LeagueSettings,
  commitContext: ImportCommitContext,
  bundledPlayers: Player[] = seedPlayers
): ImportPrepareResult {
  const errors: ImportPrepareError[] = []
  const warnings: ImportPrepareWarning[] = []
  const matchWarnings: MatchWarning[] = []

  if (!content.trim()) {
    return { ok: false, errors: [{ message: 'CSV content is empty.' }], warnings }
  }

  if (commitContext.picks.length > 0) {
    return {
      ok: false,
      errors: [{ message: 'Cannot import while draft picks exist. Reset the draft first.' }],
      warnings
    }
  }

  const parsed = Papa.parse<CsvRow>(content, { header: true, skipEmptyLines: true })
  if (parsed.errors.length) {
    return {
      ok: false,
      errors: [{ message: parsed.errors[0]?.message ?? 'CSV parse failed.' }],
      warnings
    }
  }

  const headers = parsed.meta.fields ?? []
  const headerMap = new Map(headers.map((header) => [normalizeHeader(header), header]))
  for (const required of REQUIRED_HEADERS) {
    if (!headerMap.has(required)) {
      errors.push({ field: required, message: `Missing required column '${required}'.` })
    }
  }
  if (errors.length) return { ok: false, errors, warnings }

  const matcher = new BundledPlayerMatcher(bundledPlayers)
  const parsedRows: Array<{
    rowNumber: number
    name: string
    team: string
    position: PlayerPosition
    positionRank: number
    tier?: number
    tierRank?: number
    tierSize?: number
    tierValueMultiplier?: number
    adp?: number
    adpRoundPick?: string
    riskScore?: number
    upsideScore?: number
    byeWeek?: number
    slug?: string
    importedId?: string
    sourceTags: FootballersSourceTags
    tags?: string
    season: number
    asOfDate: string
    rankingType: string
    scoringProfile: string
    leagueSize: number
    sourceCheatsheetId: string
    sourceUrl?: string
  }> = []

  const sheetMeta = {
    season: '',
    asOfDate: '',
    rankingType: '',
    scoringProfile: '',
    leagueSize: '',
    sourceCheatsheetId: '',
    sourceUrl: ''
  }

  for (const [index, row] of parsed.data.entries()) {
    const rowNumber = index + 2
    try {
      for (const value of Object.values(row)) {
        if (typeof value === 'string' && looksLikeFormula(value.trim())) {
          throw new Error('contains formula-like values')
        }
      }

      const name = rowValue(row, headerMap, 'player_name')
      const rawPosition = rowValue(row, headerMap, 'position')
      const position = normalizePosition(rawPosition)
      const positionRank = optionalInt(rowValue(row, headerMap, 'position_rank'), 'position_rank', rowNumber)
      const season = rowValue(row, headerMap, 'season')
      const asOfDate = rowValue(row, headerMap, 'as_of_date')
      const rankingType = rowValue(row, headerMap, 'ranking_type')
      const scoringProfile = rowValue(row, headerMap, 'scoring_profile')
      const leagueSize = rowValue(row, headerMap, 'league_size')
      const sourceCheatsheetId = rowValue(row, headerMap, 'source_cheatsheet_id')
      const sourceUrl = rowValue(row, headerMap, 'source_url') || undefined

      if (!name) throw new Error('player_name is required')
      if (!position) throw new Error(`unsupported position '${rawPosition}'`)
      if (!positionRank || positionRank < 1) throw new Error('position_rank must be a positive integer')

      if (!sheetMeta.season) {
        Object.assign(sheetMeta, { season, asOfDate, rankingType, scoringProfile, leagueSize, sourceCheatsheetId, sourceUrl })
      } else {
        for (const [key, expected] of Object.entries({
          season,
          asOfDate,
          rankingType,
          scoringProfile,
          leagueSize,
          sourceCheatsheetId
        })) {
          const current = sheetMeta[key as keyof typeof sheetMeta]
          if (expected && current && expected !== current) {
            throw new Error(`inconsistent ${key} across rows`)
          }
        }
      }

      const tierNumber = optionalInt(rowValue(row, headerMap, 'tier_number'), 'tier_number', rowNumber)
      const tierRank = optionalInt(rowValue(row, headerMap, 'tier_rank'), 'tier_rank', rowNumber)
      const tierSize = optionalInt(rowValue(row, headerMap, 'tier_size'), 'tier_size', rowNumber)
      const tierValueMultiplier = optionalNumber(rowValue(row, headerMap, 'tier_value_multiplier'), 'tier_value_multiplier', rowNumber)
      const adp = optionalNumber(rowValue(row, headerMap, 'adp_overall'), 'adp_overall', rowNumber)
      const adpRoundPick = rowValue(row, headerMap, 'adp_round_pick') || undefined
      const riskScore = optionalNumber(rowValue(row, headerMap, 'risk_score'), 'risk_score', rowNumber)
      const upsideScore = optionalNumber(rowValue(row, headerMap, 'upside_score'), 'upside_score', rowNumber)
      const byeWeek = optionalInt(rowValue(row, headerMap, 'bye_week'), 'bye_week', rowNumber)
      const slug = rowValue(row, headerMap, 'player_slug') || undefined
      const importedId = rowValue(row, headerMap, 'player_id') || undefined
      const tagsRaw = rowValue(row, headerMap, 'tags') || undefined
      const sourceTags = tagsFromBooleans(row, headerMap)
      const pipeTags = parseTagsField(tagsRaw ?? '')
      const booleanTags = tagSetFromRecord(sourceTags)
      const hasBooleanValues = Object.values(sourceTags).some(Boolean)
      if (pipeTags.size && hasBooleanValues) {
        if (pipeTags.size !== booleanTags.size || [...pipeTags].some((tag) => !booleanTags.has(tag))) {
          throw new Error('tags column and boolean tag fields disagree')
        }
      } else if (pipeTags.size) {
        for (const tag of pipeTags) {
          if (tag === 'my_guy') sourceTags.myGuy = true
          if (tag === 'value') sourceTags.value = true
          if (tag === 'bust') sourceTags.bust = true
          if (tag === 'sleeper') sourceTags.sleeper = true
          if (tag === 'rookie') sourceTags.rookie = true
          if (tag === 'injured') sourceTags.injured = true
          if (tag === 'breakout') sourceTags.breakout = true
        }
      }

      if (SKILL_POSITIONS.has(position)) {
        if (tierNumber === undefined || tierRank === undefined || tierSize === undefined) {
          throw new Error(`${position} row requires tier_number, tier_rank, and tier_size`)
        }
        if (tierNumber < 1 || tierRank < 1 || tierSize < 1 || tierRank > tierSize) {
          throw new Error('invalid tier membership')
        }
      }

      parsedRows.push({
        rowNumber,
        name,
        team: rowValue(row, headerMap, 'team').toUpperCase() || 'FA',
        position,
        positionRank,
        tier: tierNumber,
        tierRank,
        tierSize,
        tierValueMultiplier,
        adp,
        adpRoundPick,
        riskScore,
        upsideScore,
        byeWeek,
        slug,
        importedId,
        sourceTags,
        tags: tagsRaw,
        season: Number(season),
        asOfDate,
        rankingType,
        scoringProfile,
        leagueSize: Number(leagueSize),
        sourceCheatsheetId,
        sourceUrl
      })
    } catch (error) {
      errors.push({
        row: rowNumber,
        message: error instanceof Error ? error.message : 'Invalid row'
      })
    }
  }

  if (!parsedRows.length) {
    errors.push({ message: 'CSV contains no player rows.' })
  }

  const ranksByPosition = new Map<PlayerPosition, number[]>()
  for (const row of parsedRows) {
    const bucket = ranksByPosition.get(row.position) ?? []
    bucket.push(row.positionRank)
    ranksByPosition.set(row.position, bucket)
  }
  for (const [position, ranks] of ranksByPosition) {
    const sorted = [...ranks].sort((a, b) => a - b)
    const unique = new Set(sorted)
    if (unique.size !== sorted.length) {
      errors.push({ field: 'position_rank', message: `Duplicate ${position} position ranks found.` })
    }
    for (let expected = 1; expected <= sorted.length; expected += 1) {
      if (!unique.has(expected)) {
        errors.push({ field: 'position_rank', message: `${position} ranks must be continuous starting at 1.` })
        break
      }
    }
  }

  for (const position of SKILL_POSITIONS) {
    const rows = parsedRows.filter((row) => row.position === position)
    const tiers = new Map<number, { ranks: number[]; size?: number }>()
    for (const row of rows) {
      if (row.tier === undefined || row.tierRank === undefined || row.tierSize === undefined) continue
      const bucket = tiers.get(row.tier) ?? { ranks: [], size: row.tierSize }
      bucket.ranks.push(row.tierRank)
      if (bucket.size !== row.tierSize) {
        errors.push({ field: 'tier_size', message: `${position} tier ${row.tier} has inconsistent tier_size values.` })
      }
      tiers.set(row.tier, bucket)
    }
    for (const [tier, bucket] of tiers) {
      const uniqueRanks = new Set(bucket.ranks)
      if (uniqueRanks.size !== bucket.ranks.length) {
        errors.push({ field: 'tier_rank', message: `${position} tier ${tier} has duplicate tier_rank values.` })
      }
      if (bucket.size !== undefined && bucket.ranks.length !== bucket.size) {
        errors.push({ field: 'tier_size', message: `${position} tier ${tier} row count does not match tier_size.` })
      }
    }
  }

  if (errors.length) return { ok: false, errors, warnings }

  const identityBase = {
    season: Number(sheetMeta.season),
    asOfDate: sheetMeta.asOfDate,
    rankingType: sheetMeta.rankingType,
    scoringProfile: sheetMeta.scoringProfile,
    leagueSize: Number(sheetMeta.leagueSize),
    sourceCheatsheetId: sheetMeta.sourceCheatsheetId,
    sourceUrl: sheetMeta.sourceUrl
  }

  const positionCounts: Record<string, number> = {}
  for (const row of parsedRows) {
    positionCounts[row.position] = (positionCounts[row.position] ?? 0) + 1
  }

  errors.push(...validateLeagueCompatibility(settings, identityBase, positionCounts))

  const fingerprint = fingerprintForSheet(identityBase, parsedRows.map((row) => ({
    position: row.position,
    positionRank: row.positionRank,
    name: row.name
  })))
  const identity: ImportSourceIdentity = { ...identityBase, fingerprint, positionCounts }

  const players: Player[] = []
  const unmatched: ImportPrepareError[] = []
  for (const row of parsedRows) {
    const match = matcher.match({
      row: row.rowNumber,
      name: row.name,
      position: row.position,
      team: row.team,
      slug: row.slug,
      importedId: row.importedId
    })
    if (!match.ok) {
      if (match.reason.startsWith('no bundled projection match')) {
        warnings.push({ row: row.rowNumber, message: match.reason })
        continue
      }
      unmatched.push({ row: row.rowNumber, message: match.reason })
      continue
    }
    matchWarnings.push(...match.result.warnings)
    players.push(buildPlayer(match.result.bundled, {
      name: row.name,
      team: row.team,
      position: row.position,
      positionRank: row.positionRank,
      tier: row.tier,
      tierRank: row.tierRank,
      tierSize: row.tierSize,
      tierValueMultiplier: row.tierValueMultiplier,
      adp: row.adp,
      adpRoundPick: row.adpRoundPick,
      riskScore: row.riskScore,
      upsideScore: row.upsideScore,
      byeWeek: row.byeWeek,
      slug: row.slug,
      sourceTags: row.sourceTags,
      tags: row.tags,
      identity
    }))
  }

  if (unmatched.length) {
    errors.push(...unmatched)
  }
  if (!players.length) {
    errors.push({ message: 'CSV contains no players that match bundled projections.' })
  }

  const preparedIds = new Set(players.map((player) => player.id))
  const referenceResult = validateReferences(preparedIds, commitContext.keepers, commitContext.adjustments)
  errors.push(...referenceResult.errors)
  warnings.push(...referenceResult.warnings)

  if (errors.length) return { ok: false, errors, warnings }

  return {
    ok: true,
    players,
    identity,
    warnings,
    matchWarnings
  }
}

export async function readFootballersCsvFile(file: File): Promise<string> {
  return file.text()
}
