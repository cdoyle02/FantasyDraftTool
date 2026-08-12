import { describe, expect, it } from 'vitest'
import { teamForPick } from './draftStore'

describe('snake draft order', () => {
  it('reverses team order on alternating rounds', () => {
    expect(Array.from({ length: 12 }, (_, index) => teamForPick(index + 1, 12))).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    expect(Array.from({ length: 12 }, (_, index) => teamForPick(index + 13, 12))).toEqual([12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
    expect(teamForPick(25, 12)).toBe(1)
  })
})
