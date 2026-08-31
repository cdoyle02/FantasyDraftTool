import { describe, expect, it } from 'vitest'
import { defaultLeague, type DraftPick } from '../types'
import { assignRosterSlots, expandRosterSlots } from './rosterSlots'

function pick(partial: Pick<DraftPick, 'id' | 'pickNumber' | 'playerName' | 'position'>): DraftPick {
  return {
    teamId: 1,
    playerId: partial.id,
    timestamp: partial.pickNumber,
    ...partial
  }
}

const slots = defaultLeague.rosterSlots

describe('expandRosterSlots', () => {
  it('expands league slots in ESPN starter-then-bench order and skips empty counts', () => {
    expect(expandRosterSlots(slots)).toEqual([
      'QB', 'RB', 'RB', 'WR', 'WR', 'TE', 'FLEX', 'DST', 'K',
      'BN', 'BN', 'BN', 'BN', 'BN', 'BN'
    ].map((label) => (label === 'BN' ? 'BENCH' : label)))
    expect(expandRosterSlots({ ...slots, SUPERFLEX: 1, BENCH: 0 })).toContain('SUPERFLEX')
  })
})

describe('assignRosterSlots', () => {
  it('fills the matching starter slot first, then flex, then bench', () => {
    const assigned = assignRosterSlots([
      pick({ id: '1', pickNumber: 1, playerName: 'First RB', position: 'RB' }),
      pick({ id: '2', pickNumber: 2, playerName: 'Second RB', position: 'RB' }),
      pick({ id: '3', pickNumber: 3, playerName: 'Third RB', position: 'RB' }),
      pick({ id: '4', pickNumber: 4, playerName: 'Fourth RB', position: 'RB' })
    ], slots)

    expect(assigned.find((row) => row.slot === 'RB' && row.pick?.playerName === 'First RB')).toBeTruthy()
    expect(assigned.filter((row) => row.slot === 'RB').map((row) => row.pick?.playerName)).toEqual(['First RB', 'Second RB'])
    expect(assigned.find((row) => row.slot === 'FLEX')?.pick?.playerName).toBe('Third RB')
    expect(assigned.find((row) => row.slot === 'BENCH')?.pick?.playerName).toBe('Fourth RB')
  })

  it('keeps a QB in the QB slot instead of flex', () => {
    const assigned = assignRosterSlots([
      pick({ id: '1', pickNumber: 1, playerName: 'Starter QB', position: 'QB' }),
      pick({ id: '2', pickNumber: 2, playerName: 'Flex WR', position: 'WR' })
    ], slots)
    expect(assigned.find((row) => row.slot === 'QB')?.pick?.playerName).toBe('Starter QB')
    expect(assigned.find((row) => row.slot === 'WR')?.pick?.playerName).toBe('Flex WR')
    expect(assigned.find((row) => row.slot === 'FLEX')?.pick).toBeUndefined()
  })

  it('still returns empty starter and bench rows when nobody is drafted', () => {
    const assigned = assignRosterSlots([], slots)
    expect(assigned).toHaveLength(15)
    expect(assigned.every((row) => !row.pick)).toBe(true)
  })

  it('appends extra bench rows when the roster is overfilled', () => {
    const extras = Array.from({ length: 16 }, (_, index) =>
      pick({ id: String(index + 1), pickNumber: index + 1, playerName: `Extra ${index + 1}`, position: 'WR' })
    )
    const assigned = assignRosterSlots(extras, { ...slots, BENCH: 1 })
    expect(assigned.filter((row) => row.slot === 'WR')).toHaveLength(2)
    expect(assigned.filter((row) => row.slot === 'FLEX')).toHaveLength(1)
    expect(assigned.filter((row) => row.slot === 'BENCH').length).toBeGreaterThan(1)
    expect(assigned.every((row) => row.pick)).toBe(false)
    expect(assigned.filter((row) => row.pick).length).toBe(16)
  })
})
