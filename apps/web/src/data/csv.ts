import Papa from 'papaparse'
import type { Player } from '../types'

type CsvRow = Record<string, string>

const get = (row: CsvRow, names: string[]) => {
  const entry = Object.entries(row).find(([key]) => names.includes(key.trim().toLowerCase()))
  return entry?.[1]?.trim()
}

export function parsePlayerCsv(file: File): Promise<Player[]> {
  return new Promise((resolve, reject) => {
    Papa.parse<CsvRow>(file, {
      header: true,
      skipEmptyLines: true,
      complete: ({ data, errors }) => {
        if (errors.length) {
          reject(new Error(errors[0].message))
          return
        }
        const invalidRows = data.filter((row) => {
          const name = get(row, ['player', 'name', 'player name'])
          const position = get(row, ['pos', 'position'])?.toUpperCase()
          const projection = get(row, ['projected points', 'points', 'proj', 'fpts'])
          return !name ||
            !['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'D/ST'].includes(position ?? '') ||
            projection === undefined ||
            projection === '' ||
            !Number.isFinite(Number(projection))
        })
        if (invalidRows.length) {
          reject(new Error(`${invalidRows.length} invalid CSV row(s). Check player, position, and projected points.`))
          return
        }
        const players = data.flatMap((row, index) => {
          const name = get(row, ['player', 'name', 'player name'])
          const rawPosition = get(row, ['pos', 'position'])?.toUpperCase()
          if (!name || !['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'D/ST'].includes(rawPosition ?? '')) return []
          const position = (rawPosition === 'D/ST' ? 'DST' : rawPosition) as Player['position']
          return [{
            id: `csv-${name.toLowerCase().replace(/\W/g, '-')}-${position.toLowerCase()}-${(get(row, ['team', 'tm']) ?? 'fa').toLowerCase()}`,
            name,
            position,
            team: get(row, ['team', 'tm']) ?? 'FA',
            projectedPoints: Number(get(row, ['projected points', 'points', 'proj', 'fpts'])) || 0,
            adp: Number(get(row, ['adp', 'average draft position', 'rank'])) || index + 1,
            tier: Number(get(row, ['tier'])) || Math.ceil((index + 1) / 12)
          } satisfies Player]
        })
        if (!players.length) reject(new Error('No players found. Include Player/Name and Position columns.'))
        else resolve(players)
      },
      error: (error) => reject(error)
    })
  })
}
