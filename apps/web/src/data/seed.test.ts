import { describe, expect, it } from 'vitest'
import { SEED_VERSION, isLegacyDemoPool, seedPlayers } from './seed'

describe('bundled expert rankings seed', () => {
  it('loads a full PPR board instead of the 25-player demo', () => {
    const positions = new Set(seedPlayers.map((player) => player.position))
    expect(SEED_VERSION).toMatch(/\d/)
    expect(seedPlayers.length).toBeGreaterThanOrEqual(300)
    expect(positions).toEqual(new Set(['QB', 'RB', 'WR', 'TE', 'K', 'DST']))
    expect(seedPlayers.every((player) => !player.id.startsWith('seed-'))).toBe(true)
  })

  it('treats the old seed-* demo as a legacy pool and leaves CSV imports alone', () => {
    expect(isLegacyDemoPool(Array.from({ length: 25 }, (_, index) => ({
      id: `seed-${index + 1}`,
      name: `Demo ${index + 1}`,
      position: 'RB',
      team: 'ATL',
      projectedPoints: 200,
      adp: index + 1,
      tier: 1
    })))).toBe(true)
    expect(isLegacyDemoPool([{
      id: 'csv-bijan-robinson-rb-atl',
      name: 'Bijan Robinson',
      position: 'RB',
      team: 'ATL',
      projectedPoints: 300,
      adp: 4.2,
      tier: 1
    }])).toBe(false)
  })
})
