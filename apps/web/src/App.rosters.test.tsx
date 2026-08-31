import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { Rosters } from './App'
import { useDraftStore } from './store/draftStore'
import { defaultLeague, type DraftPick } from './types'

function pick(partial: Pick<DraftPick, 'id' | 'pickNumber' | 'playerName'>): DraftPick {
  return {
    teamId: 1,
    playerId: partial.id,
    position: 'RB',
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
})
