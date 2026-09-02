import { describe, expect, it } from 'vitest'
import { BundledPlayerMatcher } from './playerMatch'
import type { Player } from '../types'

const bundled: Player[] = [
  {
    id: 'josh-allen-buf-qb',
    name: 'Josh Allen',
    position: 'QB',
    team: 'BUF',
    projectedPoints: 366.6,
    adp: 21,
    tier: 1
  },
  {
    id: 'eagles-dst-phi-dst',
    name: 'Eagles DST',
    position: 'DST',
    team: 'PHI',
    projectedPoints: 148.6,
    adp: 122.4,
    tier: 1
  }
]

describe('BundledPlayerMatcher', () => {
  it('matches by slug and position', () => {
    const matcher = new BundledPlayerMatcher(bundled)
    const result = matcher.match({
      row: 2,
      name: 'Josh Allen',
      position: 'QB',
      team: 'BUF',
      slug: 'josh-allen'
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.result.bundled.id).toBe('josh-allen-buf-qb')
  })

  it('matches DST by team when names differ', () => {
    const matcher = new BundledPlayerMatcher(bundled)
    const result = matcher.match({
      row: 3,
      name: 'Philadelphia Eagles',
      position: 'DST',
      team: 'PHI',
      slug: 'philadelphia-eagles'
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.result.bundled.id).toBe('eagles-dst-phi-dst')
  })

  it('warns but matches when team changed but identity is unique', () => {
    const matcher = new BundledPlayerMatcher(bundled)
    const result = matcher.match({
      row: 4,
      name: 'Josh Allen',
      position: 'QB',
      team: 'NYJ',
      slug: 'josh-allen'
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.result.warnings[0]?.message).toContain('team changed')
  })

  it('matches a unique name and position when imported id, slug, and team are missing', () => {
    const matcher = new BundledPlayerMatcher(bundled)
    const result = matcher.match({
      row: 5,
      name: 'Josh Allen',
      position: 'QB',
      team: ''
    })
    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.result.bundled.id).toBe('josh-allen-buf-qb')
    expect(result.result.method).toBe('namePosition')
  })

  it('does not treat a missing name match as a team ambiguity', () => {
    const matcher = new BundledPlayerMatcher([
      ...bundled,
      {
        id: 'jahmyr-gibbs-det-rb',
        name: 'Jahmyr Gibbs',
        position: 'RB',
        team: 'DET',
        projectedPoints: 300,
        adp: 1,
        tier: 1
      },
      {
        id: 'isiah-pacheco-det-rb',
        name: 'Isiah Pacheco',
        position: 'RB',
        team: 'DET',
        projectedPoints: 180,
        adp: 40,
        tier: 3
      }
    ])
    const result = matcher.match({
      row: 6,
      name: 'Jacob Saylors',
      position: 'RB',
      team: 'DET'
    })
    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.reason).toBe('no bundled projection match for Jacob Saylors')
  })
})
