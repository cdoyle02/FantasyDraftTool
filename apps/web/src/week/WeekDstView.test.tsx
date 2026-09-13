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

describe('WeekDstView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  it('renders ranked D/ST plays from the week-odds API', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(weekPayload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )

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
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        error: { code: 'odds_unavailable', message: 'ODDS_API_KEY is not set.' }
      }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    )

    render(<WeekDstView />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('ODDS_API_KEY is not set.')
    })
  })

  it('lets the user re-sort the odds table', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(weekPayload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )

    render(<WeekDstView />)
    await waitFor(() => expect(screen.getByText('Week 1')).toBeInTheDocument())

    const sortTotal = screen.getAllByTestId('sort-total')[0]
    await user.click(sortTotal)
    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row')
    // Header + two data rows; after sorting by total asc, KC (41.5) before BUF (48).
    expect(rows[1]).toHaveTextContent('KC')
    expect(rows[2]).toHaveTextContent('BUF')
  })
})
