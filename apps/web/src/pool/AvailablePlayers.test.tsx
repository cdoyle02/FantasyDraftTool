import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useDraftStore } from '../store/draftStore'
import { defaultLeague, type Player } from '../types'
import { AvailablePlayers } from './AvailablePlayers'

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
    expect(rows.map((row) => within(row).getAllByRole('cell')[0].textContent)).toEqual([
      expect.stringContaining("Ja'Marr Chase"),
      expect.stringContaining('Bijan Robinson'),
      expect.stringContaining('CeeDee Lamb')
    ])
    expect(within(rows[0]).getAllByRole('cell')[2]).toHaveTextContent('1.4')
    expect(screen.getByRole('button', { name: 'ADP source, FantasyPros' })).toBeInTheDocument()
  })

  it('switches the visible value and sort when ESPN or Sleeper is chosen', async () => {
    const user = userEvent.setup()
    render(<AvailablePlayers />)

    await user.click(screen.getByRole('button', { name: 'ADP source, FantasyPros' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'ESPN' }))

    let rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getAllByRole('cell')[0]).toHaveTextContent('Bijan Robinson')
    expect(within(rows[0]).getAllByRole('cell')[2]).toHaveTextContent('1.5')
    expect(within(rows[2]).getAllByRole('cell')[2]).toHaveTextContent('—')

    await user.click(screen.getByRole('button', { name: 'ADP source, ESPN' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'Sleeper' }))

    rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getAllByRole('cell')[0]).toHaveTextContent("Ja'Marr Chase")
    expect(within(rows[0]).getAllByRole('cell')[2]).toHaveTextContent('1.2')
  })

  it('reverses sort from the caret and closes the menu on Escape', async () => {
    const user = userEvent.setup()
    render(<AvailablePlayers />)

    await user.click(screen.getByRole('button', { name: /Sort by FantasyPros ADP/ }))
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getAllByRole('cell')[0]).toHaveTextContent('CeeDee Lamb')

    await user.click(screen.getByRole('button', { name: 'ADP source, FantasyPros' }))
    expect(screen.getByRole('menu', { name: 'ADP source' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu', { name: 'ADP source' })).not.toBeInTheDocument()
  })
})
