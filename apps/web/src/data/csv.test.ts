import { describe, expect, it } from 'vitest'
import { prepareFootballersImport } from './footballersImport'
import {
  buildFootballersCsv,
  defaultLeagueSettings,
  leagueARows,
  leagueBRows
} from './footballersImport.fixtures'
import { seedPlayers } from './seed'

const emptyContext = {
  settings: defaultLeagueSettings,
  picks: [],
  keepers: [],
  adjustments: {}
}

describe('Footballers CSV import', () => {
  it('imports a normal skill-position row with bundled projection overlay', () => {
    const csv = buildFootballersCsv(leagueARows())
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const josh = result.players.find((player) => player.name === 'Josh Allen')
    expect(josh?.id).toBe('josh-allen-buf-qb')
    expect(josh?.projectedPoints).toBe(seedPlayers.find((player) => player.id === 'josh-allen-buf-qb')?.projectedPoints)
    expect(josh?.positionRank).toBe(1)
    expect(josh?.tier).toBe(9)
    expect(josh?.tierValueMultiplier).toBe(0.99)
    expect(josh?.adp).toBe(901)
    expect(josh?.riskScore).toBe(9.01)
    expect(josh?.upsideScore).toBe(9.91)
    expect(josh?.sourceTags?.myGuy).toBe(true)
    expect(josh?.sourceTags?.breakout).toBe(true)
  })

  it('allows blank ADP on late skill-position rows', () => {
    const csv = buildFootballersCsv([
      ...leagueARows(),
      {
        position: 'WR',
        positionRank: 1,
        playerName: 'George Pickens',
        playerSlug: 'george-pickens',
        team: 'DAL',
        tierNumber: 3,
        tierRank: 1,
        tierSize: 1,
        tierValueMultiplier: 0.8
      }
    ])
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const pickens = result.players.find((player) => player.id === 'george-pickens-dal-wr')
    expect(pickens?.adp).toBeUndefined()
  })

  it('allows blank tier and ADP metadata for DST rows', () => {
    const csv = buildFootballersCsv(leagueARows())
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const dst = result.players.find((player) => player.position === 'DST')
    expect(dst?.tier).toBe(1)
    expect(dst?.adp).toBeUndefined()
    expect(dst?.riskScore).toBeUndefined()
  })

  it('accepts a no-kicker league when K rows are absent', () => {
    const csv = buildFootballersCsv(leagueARows())
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.players.some((player) => player.position === 'K')).toBe(false)
  })

  it('rejects kicker rows when League Setup has K = 0', () => {
    const csv = buildFootballersCsv([
      ...leagueARows(),
      {
        position: 'K',
        positionRank: 1,
        playerName: 'Justin Tucker',
        playerSlug: 'justin-tucker',
        team: 'BAL'
      }
    ])
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.errors.some((error) => error.message.includes('K = 0'))).toBe(true)
  })

  it('validates multi-tag combinations', () => {
    const csv = buildFootballersCsv(leagueARows())
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const josh = result.players.find((player) => player.name === 'Josh Allen')
    expect(josh?.sourceTagsRaw).toBe('my_guy|breakout')
  })

  it('skips unmatched players instead of inventing projections', () => {
    const csv = buildFootballersCsv([
      ...leagueARows(),
      {
        position: 'RB',
        positionRank: 1,
        playerName: 'Totally Fake Player',
        playerSlug: 'totally-fake-player',
        team: 'FA',
        tierNumber: 1,
        tierRank: 1,
        tierSize: 1,
        tierValueMultiplier: 1
      }
    ])
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.players.some((player) => player.name === 'Totally Fake Player')).toBe(false)
    expect(result.warnings.some((warning) => warning.message.includes('Totally Fake Player'))).toBe(true)
  })

  it('matches unique name and position when imported metadata is blank', () => {
    const csv = buildFootballersCsv([
      {
        position: 'QB',
        positionRank: 1,
        playerName: 'Josh Allen',
        team: '',
        tierNumber: 1,
        tierRank: 1,
        tierSize: 1,
        tierValueMultiplier: 1
      },
      {
        position: 'DST',
        positionRank: 1,
        playerName: 'Philadelphia Eagles',
        playerSlug: 'philadelphia-eagles',
        team: 'PHI'
      }
    ])
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.players.find((player) => player.name === 'Josh Allen')?.id).toBe('josh-allen-buf-qb')
  })

  it('blocks stale manual adjustments that are absent from the imported pool', () => {
    const csv = buildFootballersCsv(leagueARows())
    const result = prepareFootballersImport(csv, defaultLeagueSettings, {
      ...emptyContext,
      adjustments: { 'brandon-aubrey-dal-k': { playerId: 'brandon-aubrey-dal-k', pointsDelta: 3 } }
    })
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.errors.some((error) => error.message.includes('brandon-aubrey-dal-k'))).toBe(true)
  })

  it('rejects duplicate position ranks', () => {
    const csv = buildFootballersCsv([
      ...leagueARows(),
      {
        position: 'QB',
        positionRank: 1,
        playerName: 'Lamar Jackson',
        playerSlug: 'lamar-jackson',
        team: 'BAL',
        tierNumber: 2,
        tierRank: 1,
        tierSize: 1,
        tierValueMultiplier: 0.95
      }
    ])
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.errors.some((error) => error.message.includes('Duplicate QB position ranks'))).toBe(true)
  })

  it('rejects league-size mismatches', () => {
    const csv = buildFootballersCsv(leagueARows(), { leagueSize: 12 })
    const result = prepareFootballersImport(csv, defaultLeagueSettings, emptyContext)
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.errors.some((error) => error.message.includes('league size 12'))).toBe(true)
  })

  it('replaces League A metadata with League B metadata while keeping bundled projections', () => {
    const leagueA = prepareFootballersImport(buildFootballersCsv(leagueARows()), defaultLeagueSettings, emptyContext)
    const leagueB = prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' }),
      defaultLeagueSettings,
      emptyContext
    )
    expect(leagueA.ok && leagueB.ok).toBe(true)
    if (!leagueA.ok || !leagueB.ok) return
    const aJosh = leagueA.players.find((player) => player.id === 'josh-allen-buf-qb')
    const bJosh = leagueB.players.find((player) => player.id === 'josh-allen-buf-qb')
    expect(aJosh?.tier).toBe(9)
    expect(bJosh?.tier).toBe(2)
    expect(aJosh?.projectedPoints).toBe(bJosh?.projectedPoints)
    expect(aJosh?.importSource?.sourceCheatsheetId).toBe('sheet-a')
    expect(bJosh?.importSource?.sourceCheatsheetId).toBe('sheet-b')
  })
})
