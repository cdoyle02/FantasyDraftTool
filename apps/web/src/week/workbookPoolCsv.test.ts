import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parseDfsCsv } from './workbookPoolCsv'

const fixtureDir = dirname(fileURLToPath(import.meta.url))

describe('parseDfsCsv', () => {
  it('parses DraftKings-style Name/Position/Team/Salary headers', () => {
    const sample = readFileSync(join(fixtureDir, 'fixtures', 'dk_salaries_sample.csv'), 'utf8')
    const { players, errors } = parseDfsCsv(sample)
    expect(errors).toEqual([])
    expect(players).toHaveLength(3)
    expect(players[0]).toEqual({
      name: "Ja'Marr Chase",
      position: 'WR',
      team: 'CIN',
      salary: 8200
    })
    expect(players[1]?.name).toBe('Joe Burrow')
    expect(players[2]?.salary).toBe(5500)
  })

  it('accepts FanDuel Nickname + Team column names', () => {
    const text = `Nickname,Position,Team,Salary
Patrick Mahomes,QB,KC,8500`
    const { players, errors } = parseDfsCsv(text)
    expect(errors).toEqual([])
    expect(players).toHaveLength(1)
    expect(players[0]?.name).toBe('Patrick Mahomes')
    expect(players[0]?.team).toBe('KC')
  })

  it('reports missing required columns', () => {
    const text = `Name,Salary
Player A,5000`
    const { players, errors } = parseDfsCsv(text)
    expect(players).toHaveLength(0)
    expect(errors.some((message) => message.includes('Position'))).toBe(true)
    expect(errors.some((message) => message.includes('Team'))).toBe(true)
  })

  it('skips blank lines and rows without a salary', () => {
    const text = `Name,Position,Team,Salary

Ghost,WR,NYG,
Valid,TE,NYG,3200`
    const { players, errors } = parseDfsCsv(text)
    expect(errors).toEqual([])
    expect(players).toHaveLength(1)
    expect(players[0]?.name).toBe('Valid')
  })
})
