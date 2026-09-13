import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekKView } from './WeekKView'

const leaguesPayload = {
  leagues: [{ id: '1216398267', name: 'Girls Who Ball' }]
}

const jaredRankingsPayload = {
  week: 1,
  fetchedAt: '2026-09-13T12:00:00Z',
  sourceUrl: 'https://www.fantasypros.com/nfl/rankings/jared-smola.php',
  rankings: [
    { rank: 1, player: 'Brandon Aubrey', team: 'DAL', opponent: 'at NYG', ecr: 1, vsEcr: '0' },
    { rank: 8, player: 'Evan McPherson', team: 'CIN', opponent: 'vs. TB', ecr: 5, vsEcr: '-3' },
    { rank: 14, player: 'Jake Elliott', team: 'PHI', opponent: 'vs. WAS', ecr: 15, vsEcr: '+1' }
  ]
}

const jaredAvailablePayload = {
  ...jaredRankingsPayload,
  leagueId: '1216398267',
  leagueName: 'Girls Who Ball',
  available: [
    {
      rank: 8,
      player: 'Evan McPherson',
      team: 'CIN',
      opponent: 'vs. TB',
      ecr: 5,
      vsEcr: '-3',
      status: 'FREEAGENT',
      percentOwned: 21.6
    },
    {
      rank: 14,
      player: 'Jake Elliott',
      team: 'PHI',
      opponent: 'vs. WAS',
      ecr: 15,
      vsEcr: '+1',
      status: 'FREEAGENT',
      percentOwned: 8.7
    }
  ]
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' }
  })
}

function mockApiFetch(overrides?: {
  leagues?: Response
  rankings?: Response
  available?: Response
}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.includes('/api/v1/espn/leagues')) {
      return overrides?.leagues ?? jsonResponse(leaguesPayload)
    }
    if (url.includes('/api/v1/nfl/jared-k-available')) {
      return overrides?.available ?? jsonResponse(jaredAvailablePayload)
    }
    if (url.includes('/api/v1/nfl/jared-k-rankings')) {
      return overrides?.rankings ?? jsonResponse(jaredRankingsPayload)
    }
    return jsonResponse({ error: { message: `Unhandled ${url}` } }, 500)
  })
}

describe('WeekKView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders Jared rankings from the API', async () => {
    mockApiFetch()

    render(<WeekKView />)

    await waitFor(() => {
      expect(screen.getByTestId('jared-rankings-table')).toBeInTheDocument()
    })
    expect(within(screen.getByTestId('jared-rankings-table')).getByText('Brandon Aubrey')).toBeInTheDocument()
    expect(screen.getByText(/Week 1 K/)).toBeInTheDocument()
  })

  it('auto-selects the first league and loads available kickers', async () => {
    mockApiFetch()

    render(<WeekKView />)

    await waitFor(() => {
      expect(screen.getByTestId('jared-league-select')).toHaveValue('1216398267')
    })
    await waitFor(() => {
      expect(screen.getByTestId('jared-available-table')).toBeInTheDocument()
    })
    expect(within(screen.getByTestId('jared-available-table')).getByText('Evan McPherson')).toBeInTheDocument()
  })

  it('maps available kickers for the selected league', async () => {
    const user = userEvent.setup()
    mockApiFetch()

    render(<WeekKView />)

    await waitFor(() => {
      expect(screen.getByTestId('jared-rankings-table')).toBeInTheDocument()
    })

    const select = screen.getByTestId('jared-league-select')
    await user.selectOptions(select, '1216398267')

    await waitFor(() => {
      expect(screen.getByTestId('jared-available-table')).toBeInTheDocument()
    })
    const available = screen.getByTestId('jared-available-table')
    expect(within(available).getByText('Evan McPherson')).toBeInTheDocument()
    expect(within(available).getByText('Jake Elliott')).toBeInTheDocument()
    expect(within(available).queryByText('Brandon Aubrey')).not.toBeInTheDocument()
  })

  it('shows rankings error without crashing the view', async () => {
    mockApiFetch({
      rankings: jsonResponse(
        { error: { code: 'jared_rankings_unavailable', message: 'FantasyPros scrape failed' } },
        503
      )
    })

    render(<WeekKView />)

    await waitFor(() => {
      expect(screen.getByTestId('jared-error')).toHaveTextContent('FantasyPros scrape failed')
    })
  })

  it('keeps rankings visible when available fetch fails', async () => {
    const user = userEvent.setup()
    mockApiFetch({
      available: jsonResponse(
        { error: { code: 'espn_unavailable', message: 'ESPN cookies missing' } },
        503
      )
    })

    render(<WeekKView />)

    await waitFor(() => {
      expect(screen.getByTestId('jared-rankings-table')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByTestId('jared-league-select'), '1216398267')

    await waitFor(() => {
      expect(screen.getByTestId('jared-available-error')).toHaveTextContent('ESPN cookies missing')
    })
    expect(screen.getByTestId('jared-rankings-table')).toBeInTheDocument()
  })
})
