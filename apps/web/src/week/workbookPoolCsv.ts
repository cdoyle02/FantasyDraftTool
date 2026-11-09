/**
 * Parse pasted DraftKings / FanDuel salary CSV exports for the Workbook DFS pool tab.
 *
 * DraftKings: `Name`, `Position`, `TeamAbbrev` or `Team`, `Salary`.
 * FanDuel: `Nickname` (or `Name`), `Position`, `Team`, `Salary`.
 * Salaries stay client-side until the user clicks Rank — nothing is read from disk automatically.
 */

export interface PoolPlayerInput {
  name: string
  team: string
  salary: number
  position: string
  opponent?: string
  /** Optional exact ids for non-fuzzy pool joins (API `gsisId` / `espnPlayerId`). */
  gsisId?: string
  espnPlayerId?: number
}

export interface ParseDfsCsvResult {
  players: PoolPlayerInput[]
  errors: string[]
}

const NAME_HEADERS = ['name', 'nickname', 'player']
const POSITION_HEADERS = ['position', 'pos']
const TEAM_HEADERS = ['team', 'teamabbrev', 'team abbreviation']
const SALARY_HEADERS = ['salary', 'sal']
const OPPONENT_HEADERS = ['opponent', 'opp']
const GSIS_HEADERS = ['gsisid', 'gsis_id', 'gsis id']
const ESPN_ID_HEADERS = ['espnplayerid', 'espn_player_id', 'espn id', 'playerid']

function splitCsvLine(line: string): string[] {
  const cells: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (ch === '"') {
      const next = line[i + 1]
      if (inQuotes && next === '"') {
        current += '"'
        i += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }
    if (ch === ',' && !inQuotes) {
      cells.push(current.trim())
      current = ''
      continue
    }
    current += ch
  }
  cells.push(current.trim())
  return cells
}

function normalizeHeader(value: string): string {
  return value.replace(/^\uFEFF/, '').trim().toLowerCase()
}

function findColumnIndex(headers: string[], aliases: string[]): number {
  const normalized = headers.map(normalizeHeader)
  for (const alias of aliases) {
    const index = normalized.indexOf(alias)
    if (index >= 0) return index
  }
  return -1
}

function parseSalary(raw: string): number | null {
  const cleaned = raw.replace(/[$,\s]/g, '')
  if (!cleaned) return null
  const value = Number(cleaned)
  return Number.isFinite(value) && value > 0 ? Math.round(value) : null
}

function normalizeTeam(raw: string): string {
  return raw.trim().toUpperCase()
}

function normalizePosition(raw: string): string {
  return raw.trim().toUpperCase()
}

/** Parse DK/FD-ish salary CSV text into normalized pool rows. */
export function parseDfsCsv(text: string): ParseDfsCsvResult {
  const errors: string[] = []
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0)
  if (lines.length === 0) {
    return { players: [], errors: ['CSV is empty.'] }
  }

  const headers = splitCsvLine(lines[0] ?? '')
  const nameIdx = findColumnIndex(headers, NAME_HEADERS)
  const positionIdx = findColumnIndex(headers, POSITION_HEADERS)
  const teamIdx = findColumnIndex(headers, TEAM_HEADERS)
  const salaryIdx = findColumnIndex(headers, SALARY_HEADERS)
  const opponentIdx = findColumnIndex(headers, OPPONENT_HEADERS)
  const gsisIdx = findColumnIndex(headers, GSIS_HEADERS)
  const espnIdIdx = findColumnIndex(headers, ESPN_ID_HEADERS)

  if (nameIdx < 0) errors.push('Missing player name column (Name or Nickname).')
  if (positionIdx < 0) errors.push('Missing Position column.')
  if (teamIdx < 0) errors.push('Missing Team column.')
  if (salaryIdx < 0) errors.push('Missing Salary column.')
  if (errors.length > 0) {
    return { players: [], errors }
  }

  const players: PoolPlayerInput[] = []
  for (let lineIndex = 1; lineIndex < lines.length; lineIndex += 1) {
    const cells = splitCsvLine(lines[lineIndex] ?? '')
    const name = (cells[nameIdx] ?? '').trim()
    const position = normalizePosition(cells[positionIdx] ?? '')
    const team = normalizeTeam(cells[teamIdx] ?? '')
    const salary = parseSalary(cells[salaryIdx] ?? '')
    const opponentRaw = opponentIdx >= 0 ? (cells[opponentIdx] ?? '').trim() : ''
    const gsisRaw = gsisIdx >= 0 ? (cells[gsisIdx] ?? '').trim() : ''
    const espnRaw = espnIdIdx >= 0 ? (cells[espnIdIdx] ?? '').trim() : ''

    if (!name && !position && !team) continue
    if (!name || !position || !team) {
      errors.push(`Row ${lineIndex + 1}: missing name, position, or team.`)
      continue
    }
    if (salary == null) continue

    const player: PoolPlayerInput = { name, team, salary, position }
    if (opponentRaw) {
      player.opponent = opponentRaw.toUpperCase()
    }
    if (gsisRaw) {
      player.gsisId = gsisRaw
    }
    if (espnRaw) {
      const espnId = Number(espnRaw)
      if (Number.isFinite(espnId)) {
        player.espnPlayerId = Math.round(espnId)
      }
    }
    players.push(player)
  }

  if (players.length === 0 && errors.length === 0) {
    errors.push('No valid player rows found.')
  }

  return { players, errors }
}
