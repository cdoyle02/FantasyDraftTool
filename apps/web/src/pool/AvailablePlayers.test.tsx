import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDraftStore } from '../store/draftStore'
import { defaultLeague, type Player } from '../types'
import { AvailablePlayers } from './AvailablePlayers'

vi.mock('../data/db', () => ({
  db: {
    picks: {
      put: vi.fn().mockResolvedValue(undefined),
      delete: vi.fn(),
      clear: vi.fn(),
      bulkPut: vi.fn(),
      orderBy: vi.fn(() => ({ toArray: vi.fn().mockResolvedValue([]) }))
    },
    transaction: async (...args: unknown[]) => {
      const work = args.at(-1)
      if (typeof work === 'function') return work()
    }
  },
  queueEvent: vi.fn()
}))

vi.mock('../engine/adapter', () => ({
  getRecommendations: vi.fn().mockResolvedValue({ recommendations: [], mode: 'development-fallback' }),
  prepareOfflineEngine: vi.fn().mockRejectedValue(new Error('offline skipped in unit test'))
}))

function player(partial: Partial<Player> & Pick<Player, 'id' | 'name' | 'adp'>): Player {
  return {
    position: 'WR',
    team: 'CIN',
    projectedPoints: 300,
    tier: 1,
    ...partial
  }
}

const pool: Player[] = [
  player({ id: 'chase', name: "Ja'Marr Chase", adp: 1.4, espnAdp: 2.1, sleeperAdp: 1.2 }),
  player({ id: 'bijan', name: 'Bijan Robinson', position: 'RB', team: 'ATL', adp: 2.1, espnAdp: 1.5 }),
  player({ id: 'lamb', name: 'CeeDee Lamb', team: 'DAL', adp: 5.1, sleeperAdp: 3.4 })
]

describe('available players ADP source', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    useDraftStore.setState({
      players: pool,
      adjustments: {},
      picks: [],
      settings: defaultLeague
    })
  })

  it('keeps one ADP column and defaults to FantasyPros order', () => {
    render(<AvailablePlayers />)
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows.map((row) => within(row).getAllByRole('cell')[1].textContent)).toEqual([
      expect.stringContaining("Ja'Marr Chase"),
      expect.stringContaining('Bijan Robinson'),
      expect.stringContaining('CeeDee Lamb')
    ])
    expect(within(rows[0]).getAllByRole('cell')[3]).toHaveTextContent('1.4')
    expect(screen.getByRole('button', { name: 'ADP source, FantasyPros' })).toBeInTheDocument()
  })

  it('switches the visible value and sort when ESPN or Sleeper is chosen', async () => {
    const user = userEvent.setup()
    render(<AvailablePlayers />)

    await user.click(screen.getByRole('button', { name: 'ADP source, FantasyPros' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'ESPN' }))

    let rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getAllByRole('cell')[1]).toHaveTextContent('Bijan Robinson')
    expect(within(rows[0]).getAllByRole('cell')[3]).toHaveTextContent('1.5')
    expect(within(rows[2]).getAllByRole('cell')[3]).toHaveTextContent('—')

    await user.click(screen.getByRole('button', { name: 'ADP source, ESPN' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'Sleeper' }))

    rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getAllByRole('cell')[1]).toHaveTextContent("Ja'Marr Chase")
    expect(within(rows[0]).getAllByRole('cell')[3]).toHaveTextContent('1.2')
  })

  it('reverses sort from the caret and closes the menu on Escape', async () => {
    const user = userEvent.setup()
    render(<AvailablePlayers />)

    await user.click(screen.getByRole('button', { name: /Sort by FantasyPros ADP/ }))
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getAllByRole('cell')[1]).toHaveTextContent('CeeDee Lamb')

    await user.click(screen.getByRole('button', { name: 'ADP source, FantasyPros' }))
    expect(screen.getByRole('menu', { name: 'ADP source' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu', { name: 'ADP source' })).not.toBeInTheDocument()
  })
})

describe('player pool draft button', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    useDraftStore.setState({
      players: pool,
      adjustments: {},
      picks: [],
      settings: { ...defaultLeague, teamCount: 4, userTeam: 6 }
    })
  })

  it('labels the draft button for the on-clock team', () => {
    render(<AvailablePlayers />)
    expect(screen.getAllByRole('button', { name: /Draft .* to Team 1/ })).toHaveLength(3)
    expect(screen.queryByRole('button', { name: /to your team/ })).not.toBeInTheDocument()
  })

  it('shows YOU when your team is on the clock', () => {
    useDraftStore.setState({
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 }
    })
    render(<AvailablePlayers />)
    expect(screen.getAllByRole('button', { name: /Draft .* to your team/ })).toHaveLength(3)
  })

  it('drafts the player, removes them from the pool, and advances the clock label', async () => {
    const user = userEvent.setup()
    render(<AvailablePlayers />)
    expect(screen.getByText("Ja'Marr Chase")).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: "Draft Ja'Marr Chase to Team 1" }))
    expect(screen.queryByText("Ja'Marr Chase")).not.toBeInTheDocument()
    expect(useDraftStore.getState().picks).toHaveLength(1)
    expect(useDraftStore.getState().picks[0].playerId).toBe('chase')
    expect(useDraftStore.getState().picks[0].teamId).toBe(1)
    expect(screen.getAllByRole('button', { name: /Draft .* to Team 2/ })).toHaveLength(2)
  })
})
