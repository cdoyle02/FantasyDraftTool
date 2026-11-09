import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekSosView } from './WeekSosView'
import type { StrengthOfScheduleResponse } from './types'

function cell(week: number, opponent: string | null, rank: number | null, bye = false, inWindow = true) {
  return {
    week,
    opponent,
    opponentRank: rank,
    opponentValue: rank == null ? null : 32 - (rank - 1),
    bye,
    inWindow
  }
}

function buildPayload(overrides: Partial<StrengthOfScheduleResponse> = {}): StrengthOfScheduleResponse {
  const weeks = Array.from({ length: 18 }, (_, i) => {
    const week = i + 1
    if (week === 3) return cell(week, null, null, true, week >= 10)
    return cell(week, 'DAL', week === 1 ? 2 : 5, false, week >= 10)
  })
  return {
    season: 2026,
    position: 'RB',
    metric: 'fpa',
    startWeek: 10,
    endWeek: 17,
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    teams: [
      {
        team: 'CHI',
        rank: 1,
        opponentAverage: 22.4,
        weeks
      },
      {
        team: 'GB',
        rank: 2,
        opponentAverage: 18.1,
        weeks: weeks.map((w) => ({ ...w, opponent: w.bye ? null : 'MIN' }))
      }
    ],
    ...overrides
  }
}

describe('WeekSosView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        expect(url).toContain('/api/v1/nfl/strength-of-schedule')
        const params = new URL(url, 'http://localhost').searchParams
        const position = params.get('position') ?? 'RB'
        const metric = params.get('metric') ?? 'fpa'
        return new Response(
          JSON.stringify(
            buildPayload({
              position: position as StrengthOfScheduleResponse['position'],
              metric: metric as StrengthOfScheduleResponse['metric'],
              startWeek: Number(params.get('startWeek') ?? 10),
              endWeek: Number(params.get('endWeek') ?? 17)
            })
          ),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      })
    )
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('loads the grid with easiest schedule first and a bye cell', async () => {
    render(<WeekSosView />)
    await waitFor(() => {
      expect(screen.getByTestId('sos-table')).toBeInTheDocument()
    })
    const rows = screen.getAllByTestId(/sos-row-/)
    expect(rows[0]).toHaveAttribute('data-testid', 'sos-row-CHI')
    expect(screen.getByTestId('sos-cell-CHI-3')).toHaveTextContent('—')
    expect(screen.getByTestId('sos-source-line')).toHaveTextContent('rated through week 9')
  })

  it('refetches when switching to PAE, DST, or a custom week range', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())

    fireEvent.change(screen.getByTestId('sos-metric'), { target: { value: 'pae' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('metric=pae'))).toBe(true)
    })

    fireEvent.change(screen.getByTestId('sos-position'), { target: { value: 'DST' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('position=DST') && url.includes('metric=pae'))).toBe(true)
    })

    fireEvent.change(screen.getByTestId('sos-start-week'), { target: { value: '12' } })
    fireEvent.change(screen.getByTestId('sos-end-week'), { target: { value: '12' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(
        calls.some((url) => url.includes('startWeek=12') && url.includes('endWeek=12'))
      ).toBe(true)
    })
  })
})
