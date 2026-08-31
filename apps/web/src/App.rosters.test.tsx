import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { Rosters } from './App'
import { useDraftStore } from './store/draftStore'
import { defaultLeague, type DraftPick } from './types'

function pick(partial: Pick<DraftPick, 'id' | 'pickNumber' | 'playerName'> & Partial<Pick<DraftPick, 'position'>>): DraftPick {
  return {
    teamId: 1,
    playerId: partial.id,
    position: partial.position ?? 'RB',
    timestamp: partial.pickNumber,
    ...partial
  }
}

describe('snake board rosters', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    useDraftStore.setState({
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 },
      picks: [
        pick({ id: '1', pickNumber: 1, playerName: 'Alpha Runner' }),
        pick({ id: '2', pickNumber: 2, playerName: 'Bravo Receiver' }),
        pick({ id: '5', pickNumber: 5, playerName: 'Echo Back' })
      ]
    })
  })

  it('shows every team\'s pick for the round, even when teamId is wrong', () => {
    render(<Rosters />)
    expect(screen.getByTestId('snake-board')).toHaveTextContent('Alpha Runner')
    expect(screen.getByTestId('snake-board')).toHaveTextContent('Bravo Receiver')
    expect(screen.getByTestId('snake-board')).toHaveTextContent('Echo Back')
    expect(screen.getByTestId('snake-board')).toHaveTextContent('R1')
    expect(screen.getByTestId('snake-board')).toHaveTextContent('R2')
  })

  it('lets a collapsed team stay open so its roster is visible', async () => {
    const user = userEvent.setup()
    render(<Rosters />)
    const team2 = screen.getByTestId('roster-team-2')
    expect(team2).not.toHaveAttribute('open')
    await user.click(within(team2).getByText('Team 2'))
    expect(team2).toHaveAttribute('open')
    expect(team2).toHaveTextContent('R1')
    expect(team2).toHaveTextContent('Bravo Receiver')
  })

  it('shows only the selected team picks in team view', async () => {
    const user = userEvent.setup()
    render(<Rosters />)
    await user.click(screen.getByTestId('roster-view-team'))
    const detail = screen.getByTestId('roster-team-detail-1')
    expect(detail).toHaveTextContent('Alpha Runner')
    expect(detail).not.toHaveTextContent('Bravo Receiver')
    expect(detail).not.toHaveTextContent('Echo Back')
    expect(screen.getByTestId('roster-slot-RB-0')).toHaveTextContent('Alpha Runner')
    expect(screen.getByTestId('roster-slot-QB-0')).toHaveTextContent('—')
    expect(screen.getByTestId('team-lineup')).toHaveTextContent('FLEX')
    expect(screen.getByTestId('team-lineup')).toHaveTextContent('BN')
    await user.click(screen.getByTestId('roster-team-chip-4'))
    expect(screen.getByTestId('roster-team-detail-4')).toHaveTextContent('Echo Back')
    expect(screen.getByTestId('roster-slot-RB-0')).toHaveTextContent('Echo Back')
  })

  it('switches team picks when selecting another team chip', async () => {
    const user = userEvent.setup()
    render(<Rosters />)
    await user.click(screen.getByTestId('roster-view-team'))
    await user.click(screen.getByTestId('roster-team-chip-2'))
    const detail = screen.getByTestId('roster-team-detail-2')
    expect(detail).toHaveTextContent('Bravo Receiver')
    expect(detail).not.toHaveTextContent('Alpha Runner')
    expect(detail).not.toHaveTextContent('Echo Back')
  })

  it('puts extra position players into flex then bench', async () => {
    useDraftStore.setState({
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 },
      picks: [
        pick({ id: '1', pickNumber: 1, playerName: 'First RB', position: 'RB' }),
        pick({ id: '8', pickNumber: 8, playerName: 'Second RB', position: 'RB' }),
        pick({ id: '9', pickNumber: 9, playerName: 'Third RB', position: 'RB' }),
        pick({ id: '16', pickNumber: 16, playerName: 'Fourth RB', position: 'RB' })
      ]
    })
    const user = userEvent.setup()
    render(<Rosters />)
    await user.click(screen.getByTestId('roster-view-team'))
    expect(screen.getByTestId('roster-slot-RB-0')).toHaveTextContent('First RB')
    expect(screen.getByTestId('roster-slot-RB-1')).toHaveTextContent('Second RB')
    expect(screen.getByTestId('roster-slot-FLEX-0')).toHaveTextContent('Third RB')
    expect(screen.getByTestId('roster-slot-BENCH-0')).toHaveTextContent('Fourth RB')
  })

  it('opens team view when clicking view roster on a board row', async () => {
    const user = userEvent.setup()
    render(<Rosters />)
    await user.click(screen.getByTestId('view-team-2'))
    expect(screen.getByTestId('roster-view-team')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('roster-team-detail-2')).toHaveTextContent('Bravo Receiver')
  })

  it('highlights the team on the clock in board view', () => {
    render(<Rosters />)
    expect(screen.getByTestId('roster-team-4')).toHaveAttribute('data-on-clock', 'true')
    expect(screen.getByTestId('roster-team-1')).not.toHaveAttribute('data-on-clock')
    expect(screen.getByTestId('roster-team-2')).not.toHaveAttribute('data-on-clock')
    expect(screen.getByTestId('roster-team-3')).not.toHaveAttribute('data-on-clock')
    expect(screen.getByTestId('roster-team-4')).toHaveTextContent('ON CLOCK')
  })

  it('moves on-clock highlight after the next pick', () => {
    useDraftStore.setState({
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 },
      picks: [
        pick({ id: '1', pickNumber: 1, playerName: 'Alpha Runner' }),
        pick({ id: '2', pickNumber: 2, playerName: 'Bravo Receiver' }),
        pick({ id: '3', pickNumber: 3, playerName: 'Charlie Back' }),
        pick({ id: '4', pickNumber: 4, playerName: 'Delta Tight' })
      ]
    })
    render(<Rosters />)
    expect(screen.getByTestId('roster-team-4')).toHaveAttribute('data-on-clock', 'true')
    expect(screen.getByTestId('roster-team-1')).not.toHaveAttribute('data-on-clock')
  })

  it('shows both YOU and ON CLOCK when user team is on the clock', () => {
    useDraftStore.setState({
      settings: { ...defaultLeague, teamCount: 4, userTeam: 1 },
      picks: []
    })
    render(<Rosters />)
    const team1 = screen.getByTestId('roster-team-1')
    expect(team1).toHaveAttribute('data-on-clock', 'true')
    expect(team1).toHaveTextContent('YOU')
    expect(team1).toHaveTextContent('ON CLOCK')
  })
})
