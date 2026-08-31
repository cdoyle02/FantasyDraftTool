import { describe, expect, it } from 'vitest'
import type { Player } from '../types'
import { adpForSource, compareAvailablePlayers, formatAdp } from './adp'

function player(partial: Partial<Player> & Pick<Player, 'id' | 'name'>): Player {
  return {
    position: 'RB',
    team: 'ATL',
    projectedPoints: 200,
    adp: 10,
    tier: 1,
    ...partial
  }
}

describe('player pool ADP helpers', () => {
  it('reads the selected source and hides missing values', () => {
    const bijan = player({ id: 'bijan', name: 'Bijan', adp: 4.2, espnAdp: 3.8 })
    expect(adpForSource(bijan, 'adp')).toBe(4.2)
    expect(adpForSource(bijan, 'espnAdp')).toBe(3.8)
    expect(adpForSource(bijan, 'sleeperAdp')).toBeUndefined()
    expect(formatAdp(undefined)).toBe('—')
    expect(formatAdp(3.8)).toBe('3.8')
  })

  it('sorts by FantasyPros ADP with the boost/fade nudge by default', () => {
    const early = player({ id: 'a', name: 'Alpha', adp: 5 })
    const later = player({ id: 'b', name: 'Bravo', adp: 6 })
    expect(compareAvailablePlayers(early, later, 'adp', 'asc', {})).toBeLessThan(0)
    expect(compareAvailablePlayers(later, early, 'adp', 'asc', {
      b: { pointsDelta: 20 }
    })).toBeLessThan(0)
  })

  it('sorts by ESPN or Sleeper and puts missing values last', () => {
    const espnEarly = player({ id: 'a', name: 'Alpha', adp: 20, espnAdp: 2 })
    const espnLate = player({ id: 'b', name: 'Bravo', adp: 3, espnAdp: 8 })
    const missing = player({ id: 'c', name: 'Charlie', adp: 1 })
    const sleeper = player({ id: 'd', name: 'Delta', adp: 12, sleeperAdp: 4 })

    expect(compareAvailablePlayers(espnEarly, espnLate, 'espnAdp', 'asc', {})).toBeLessThan(0)
    expect(compareAvailablePlayers(espnLate, espnEarly, 'espnAdp', 'desc', {})).toBeLessThan(0)
    expect(compareAvailablePlayers(missing, espnEarly, 'espnAdp', 'asc', {})).toBeGreaterThan(0)
    expect(compareAvailablePlayers(espnEarly, missing, 'espnAdp', 'asc', {})).toBeLessThan(0)
    expect(compareAvailablePlayers(sleeper, espnEarly, 'sleeperAdp', 'asc', {})).toBeLessThan(0)
  })
})
