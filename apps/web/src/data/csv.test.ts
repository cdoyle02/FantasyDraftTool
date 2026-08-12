import { describe, expect, it } from 'vitest'
import { parsePlayerCsv } from './csv'

describe('player CSV import', () => {
  it('normalizes FantasyPros-style rows to stable player IDs', async () => {
    const file = new File(
      ['Player,Team,POS,FPTS,ADP,Tier\nBijan Robinson,ATL,RB,300,4.2,1\n'],
      'players.csv',
      { type: 'text/csv' }
    )

    const [player] = await parsePlayerCsv(file)
    expect(player.id).toBe('csv-bijan-robinson-rb-atl')
    expect(player.projectedPoints).toBe(300)
  })

  it('rejects malformed rows instead of silently importing zero projections', async () => {
    const file = new File(
      ['Player,Team,POS,FPTS\nBroken Player,ATL,RB,not-a-number\n'],
      'players.csv',
      { type: 'text/csv' }
    )

    await expect(parsePlayerCsv(file)).rejects.toThrow('1 invalid CSV row')
  })
})
