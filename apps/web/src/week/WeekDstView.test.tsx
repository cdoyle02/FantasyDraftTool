import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekDstView } from './WeekDstView'

const weekPayload = {
  week: 1,
  windowStart: '2026-09-08T00:00:00-04:00',
  windowEnd: '2026-09-14T23:59:59.999999-04:00',
  fetchedAt: '2026-09-12T17:00:00Z',
  games: [
    {
      homeTeam: 'KC',
      awayTeam: 'LV',
      commenceTime: '2026-09-13T17:00:00Z',
      spread: -9.5,
      total: 41.5,
      favoriteTeam: 'KC',
      underdogTeam: 'LV',
      favoriteImplied: 25.5,
      underdogImplied: 16.0,
      dstPlayTeam: 'KC',
      bookmaker: 'consensus'
    },
    {
      homeTeam: 'BUF',
      awayTeam: 'MIA',
      commenceTime: '2026-09-13T20:00:00Z',
      spread: -3.0,
      total: 48.0,
      favoriteTeam: 'BUF',
      underdogTeam: 'MIA',
      favoriteImplied: 25.5,
      underdogImplied: 22.5,
      dstPlayTeam: 'BUF',
      bookmaker: 'consensus'
    }
  ]
}

const leaguesPayload = {
  leagues: [{ id: '1216398267', name: 'Girls Who Ball' }]
}

const kyleRankingsPayload = {
  week: 1,
  fetchedAt: '2026-09-13T12:00:00Z',
  sourceUrl: 'https://www.fantasypros.com/nfl/rankings/kyle-krajewski.php',
  rankings: [
    { rank: 1, team: 'JAX', teamName: 'Jacksonville Jaguars', opponent: 'vs. CLE', ecr: 1, vsEcr: '0' },
    { rank: 2, team: 'LAC', teamName: 'Los Angeles Chargers', opponent: 'vs. ARI', ecr: 2, vsEcr: '0' },
    { rank: 3, team: 'TEN', teamName: 'Tennessee Titans', opponent: 'vs. NYJ', ecr: 10, vsEcr: '+7' }
  ]
}

const kyleAvailablePayload = {
  ...kyleRankingsPayload,
  leagueId: '1216398267',
  leagueName: 'Girls Who Ball',
  available: [
    {
      rank: 1,
      team: 'JAX',
      teamName: 'Jacksonville Jaguars',
      opponent: 'vs. CLE',
      ecr: 1,
      vsEcr: '0',
      status: 'FREEAGENT',
      percentOwned: 11.0
    },
    {
      rank: 3,
      team: 'TEN',
      teamName: 'Tennessee Titans',
      opponent: 'vs. NYJ',
      ecr: 10,
      vsEcr: '+7',
      status: 'WAIVERS',
      percentOwned: 3.0
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
  odds?: Response
  leagues?: Response
  rankings?: Response
  available?: Response
}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.includes('/api/v1/nfl/week-odds')) {
      return overrides?.odds ?? jsonResponse(weekPayload)
    }
    if (url.includes('/api/v1/espn/leagues')) {
      return overrides?.leagues ?? jsonResponse(leaguesPayload)
    }
    if (url.includes('/api/v1/nfl/kyle-dst-available')) {
      return overrides?.available ?? jsonResponse(kyleAvailablePayload)
    }
    if (url.includes('/api/v1/nfl/kyle-dst-rankings')) {
      return overrides?.rankings ?? jsonResponse(kyleRankingsPayload)
    }
    return jsonResponse({ error: { message: `Unhandled ${url}` } }, 500)
  })
}

describe('WeekDstView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders ranked D/ST plays from the week-odds API', async () => {
    mockApiFetch()

    render(<WeekDstView />)

    await waitFor(() => {
      expect(screen.getByText('Week 1')).toBeInTheDocument()
    })
    expect(screen.getByTestId('dst-play-KC')).toBeInTheDocument()
    expect(screen.getByTestId('dst-play-BUF')).toBeInTheDocument()
    const cards = screen.getAllByTestId(/dst-play-/)
    expect(cards[0]).toHaveAttribute('data-testid', 'dst-play-KC')
  })

  it('shows API error message when odds are unavailable', async () => {
    mockApiFetch({
      odds: jsonResponse(
        { error: { code: 'odds_unavailable', message: 'ODDS_API_KEY is not set.' } },
        503
      )
    })

    render(<WeekDstView />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('ODDS_API_KEY is not set.')
    })
  })

  it('lets the user re-sort the odds table', async () => {
    const user = userEvent.setup()
    mockApiFetch()

    render(<WeekDstView />)
    await waitFor(() => expect(screen.getByText('Week 1')).toBeInTheDocument())

    const sortTotal = screen.getAllByTestId('sort-total')[0]
    await user.click(sortTotal)
    const table = screen.getByTestId('week-odds-table')
    const rows = within(table).getAllByRole('row')
    // Header + two data rows; after sorting by total asc, KC (41.5) before BUF (48).
    expect(rows[1]).toHaveTextContent('KC')
    expect(rows[2]).toHaveTextContent('BUF')
  })

  it('shows implied points allowed for both defenses', async () => {
    mockApiFetch()

    render(<WeekDstView />)
    await waitFor(() => expect(screen.getByText('Week 1')).toBeInTheDocument())

    expect(screen.getByTestId('sort-fav-dst-pa')).toHaveTextContent(/Fav D\/ST PA/)
    expect(screen.getByTestId('sort-dog-dst-pa')).toHaveTextContent(/Dog D\/ST PA/)

    const table = screen.getByTestId('week-odds-table')
    const rows = within(table).getAllByRole('row')
    // KC fav D/ST PA = underdogImplied 16.0; dog (LV) D/ST PA = favoriteImplied 25.5
    expect(rows[1]).toHaveTextContent('16.0')
    expect(rows[1]).toHaveTextContent('25.5')
  })

  it('renders Kyle rankings and available defenses for the selected league', async () => {
    const user = userEvent.setup()
    mockApiFetch()

    render(<WeekDstView />)

    await waitFor(() => {
      expect(screen.getByTestId('kyle-rankings-table')).toBeInTheDocument()
    })
    expect(within(screen.getByTestId('kyle-rankings-table')).getByText('JAX')).toBeInTheDocument()

    const select = screen.getByTestId('kyle-league-select')
    await user.selectOptions(select, '1216398267')

    await waitFor(() => {
      expect(screen.getByTestId('kyle-available-table')).toBeInTheDocument()
    })
    const available = screen.getByTestId('kyle-available-table')
    expect(within(available).getByText('JAX')).toBeInTheDocument()
    expect(within(available).getByText('TEN')).toBeInTheDocument()
    expect(within(available).queryByText('LAC')).not.toBeInTheDocument()
  })

  it('keeps odds visible when Kyle rankings fail', async () => {
    mockApiFetch({
      rankings: jsonResponse(
        { error: { code: 'kyle_rankings_unavailable', message: 'FantasyPros scrape failed' } },
        503
      )
    })

    render(<WeekDstView />)

    await waitFor(() => expect(screen.getByTestId('dst-play-KC')).toBeInTheDocument())
    await waitFor(() => {
      expect(screen.getByTestId('kyle-error')).toHaveTextContent('FantasyPros scrape failed')
    })
  })
})
