import { describe, expect, it } from 'vitest'
import { serializeRecommendationRequest } from '../api/client'
import { prepareFootballersImport } from './footballersImport'
import {
  buildFootballersCsv,
  defaultLeagueSettings,
  leagueARows,
  leagueBRows
} from './footballersImport.fixtures'

describe('Footballers import to DVS request wiring', () => {
  it('keeps full CSV-owned metadata on the active player while only sending existing DVS fields', () => {
    const prepared = prepareFootballersImport(
      buildFootballersCsv(leagueARows()),
      defaultLeagueSettings,
      { settings: defaultLeagueSettings, picks: [], keepers: [], adjustments: {} }
    )
    expect(prepared.ok).toBe(true)
    if (!prepared.ok) return
    const player = prepared.players.find((item) => item.id === 'josh-allen-buf-qb')
    expect(player).toBeTruthy()
    expect(player?.positionRank).toBe(1)
    expect(player?.tierValueMultiplier).toBe(0.99)
    expect(player?.riskScore).toBe(9.01)

    const payload = serializeRecommendationRequest({
      players: prepared.players,
      picks: [],
      keepers: [],
      settings: defaultLeagueSettings,
      adjustments: []
    })
    const requestPlayer = payload.players.find((item) => item.id === 'josh-allen-buf-qb')
    expect(requestPlayer?.projectedPoints).toBe(player?.projectedPoints)
    expect(requestPlayer?.tier).toBe(9)
    expect(requestPlayer?.adp).toBe(901)
    expect(requestPlayer?.upsideScore).toBe(9.91)
    expect(requestPlayer?.riskScore).toBe(9.01)
  })

  it('updates only existing DVS-consumed fields after League B replacement', () => {
    const leagueA = prepareFootballersImport(
      buildFootballersCsv(leagueARows()),
      defaultLeagueSettings,
      { settings: defaultLeagueSettings, picks: [], keepers: [], adjustments: {} }
    )
    const leagueB = prepareFootballersImport(
      buildFootballersCsv(leagueBRows(), { sourceCheatsheetId: 'sheet-b' }),
      defaultLeagueSettings,
      { settings: defaultLeagueSettings, picks: [], keepers: [], adjustments: {} }
    )
    expect(leagueA.ok && leagueB.ok).toBe(true)
    if (!leagueA.ok || !leagueB.ok) return

    const payloadA = serializeRecommendationRequest({
      players: leagueA.players,
      picks: [],
      keepers: [],
      settings: defaultLeagueSettings,
      adjustments: []
    })
    const payloadB = serializeRecommendationRequest({
      players: leagueB.players,
      picks: [],
      keepers: [],
      settings: defaultLeagueSettings,
      adjustments: []
    })
    const a = payloadA.players.find((item) => item.id === 'josh-allen-buf-qb')
    const b = payloadB.players.find((item) => item.id === 'josh-allen-buf-qb')
    expect(a?.tier).toBe(9)
    expect(b?.tier).toBe(2)
    expect(a?.adp).toBe(901)
    expect(b?.adp).toBe(802)
    expect(a?.projectedPoints).toBe(b?.projectedPoints)
    expect(payloadA.settings.formulaVersion).toBe(4)
    expect(payloadB.settings.formulaVersion).toBe(4)
  })
})
