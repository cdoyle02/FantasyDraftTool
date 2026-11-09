import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekSosView } from './WeekSosView'
import type { StrengthOfScheduleResponse, StrengthOfScheduleTier1Response } from './types'

function classicCell(week: number, opponent: string | null, rank: number | null, bye = false, inWindow = true) {
  return {
    week,
    opponent,
    opponentRank: rank,
    opponentValue: rank == null ? null : 32 - (rank - 1),
    bye,
    inWindow
  }
}

function tier1Cell(
  week: number,
  opponent: string | null,
  rank: number | null,
  softness: 'soft' | 'neutral' | 'tough' | null = 'neutral',
  bye = false,
  inWindow = true
) {
  const score = softness === 'soft' ? 1 : softness === 'tough' ? 0 : softness === 'neutral' ? 0.5 : null
  return {
    week,
    opponent,
    shrunkAfpa: rank == null ? null : 20 + (32 - rank),
    rank,
    softness,
    softnessScore: score,
    bye,
    inWindow
  }
}

function buildClassicPayload(overrides: Partial<StrengthOfScheduleResponse> = {}): StrengthOfScheduleResponse {
  const weeks = Array.from({ length: 18 }, (_, i) => {
    const week = i + 1
    if (week === 3) return classicCell(week, null, null, true, week >= 10)
    return classicCell(week, 'DAL', week === 1 ? 2 : 5, false, week >= 10)
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

function buildTier1Payload(
  overrides: Partial<StrengthOfScheduleTier1Response> = {}
): StrengthOfScheduleTier1Response {
  const weeks = Array.from({ length: 18 }, (_, i) => {
    const week = i + 1
    if (week === 3) return tier1Cell(week, null, null, null, true, week >= 10)
    return tier1Cell(week, 'DAL', week === 1 ? 2 : 5, 'soft', false, week >= 10)
  })
  return {
    season: 2026,
    position: 'RB',
    window: 'l8',
    startWeek: 10,
    endWeek: 17,
    ratedThroughWeek: 9,
    ratingWeeks: [2, 3, 4, 5, 6, 7, 8, 9],
    shrinkK: 4,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    teams: [
      {
        team: 'CHI',
        rank: 1,
        opponentAverage: 22.4,
        weeks
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
        if (url.includes('/strength-of-schedule/tier1')) {
          const params = new URL(url, 'http://localhost').searchParams
          const position = params.get('position') ?? 'RB'
          const window = (params.get('window') ?? 'l8') as StrengthOfScheduleTier1Response['window']
          return new Response(
            JSON.stringify(
              buildTier1Payload({
                position: position as StrengthOfScheduleTier1Response['position'],
                window,
                startWeek: Number(params.get('startWeek') ?? 10),
                endWeek: Number(params.get('endWeek') ?? 17)
              })
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        expect(url).toContain('/api/v1/nfl/strength-of-schedule')
        const params = new URL(url, 'http://localhost').searchParams
        const position = params.get('position') ?? 'RB'
        const metric = params.get('metric') ?? 'fpa'
        return new Response(
          JSON.stringify(
            buildClassicPayload({
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

  it('loads tier1 grid with softness badges and rated-through line', async () => {
    render(<WeekSosView />)
    await waitFor(() => {
      expect(screen.getByTestId('sos-table')).toBeInTheDocument()
    })
    expect(screen.getByTestId('sos-badge-CHI-1')).toHaveTextContent('S')
    expect(screen.getByTestId('sos-source-line')).toHaveTextContent('shrink k=4')
    expect(screen.getByTestId('sos-source-line')).toHaveTextContent('rated through week 9')
  })

  it('refetches tier1 with window=l4 when L4 is selected', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('sos-rating-l4'))
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((u) => u.includes('/tier1') && u.includes('window=l4'))).toBe(true)
    })
  })

  it('refetches when switching to classic PAE, DST, or a custom week range', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())

    fireEvent.change(screen.getByTestId('sos-view-mode'), { target: { value: 'classic' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('metric=fpa') && !url.includes('/tier1'))).toBe(true)
    })

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
