import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekSosView } from './WeekSosView'
import type {
  StrengthOfScheduleResponse,
  StrengthOfScheduleTier1Response,
  StrengthOfScheduleTier2Response
} from './types'

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

function buildTier2Payload(
  overrides: Partial<StrengthOfScheduleTier2Response> = {}
): StrengthOfScheduleTier2Response {
  const payload = buildTier1Payload({ position: 'RB' })
  const weeks = payload.teams[0].weeks.map((cell) => ({
    week: cell.week,
    opponent: cell.opponent,
    shrunkEpa: cell.shrunkAfpa,
    rank: cell.rank,
    softness: cell.softness,
    softnessScore: cell.softnessScore,
    bye: cell.bye,
    inWindow: cell.inWindow
  }))
  return {
    season: payload.season,
    position: 'RB',
    window: payload.window,
    startWeek: payload.startWeek,
    endWeek: payload.endWeek,
    ratedThroughWeek: payload.ratedThroughWeek,
    ratingWeeks: payload.ratingWeeks,
    shrinkK: payload.shrinkK,
    softnessMetric: 'epa_allowed',
    fetchedAt: payload.fetchedAt,
    source: payload.source,
    stale: payload.stale,
    teams: [{ ...payload.teams[0], weeks }],
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
        if (url.includes('/espn/leagues')) {
          return new Response(
            JSON.stringify({
              leagues: [{ id: '1216398267', name: 'Girls Who Ball' }]
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        if (url.includes('/strength-of-schedule/tier2/opportunity')) {
          const params = new URL(url, 'http://localhost').searchParams
          const position = params.get('position') ?? 'RB'
          return new Response(
            JSON.stringify({
              season: 2026,
              position,
              window: params.get('window') ?? 'l8',
              week: Number(params.get('week') ?? 10),
              ratedThroughWeek: 9,
              ratingWeeks: [2, 3, 4, 5, 6, 7, 8, 9],
              shrinkK: 4,
              softnessMetric: 'epa_allowed',
              minOffenseSnapPct: 0.2,
              snapFiltered: true,
              gameScriptApplied: false,
              fetchedAt: '2026-11-08T12:00:00Z',
              source: 'nflverse',
              stale: false,
              players: [
                {
                  name: 'Workhorse',
                  team: 'CHI',
                  position: 'RB',
                  week: 10,
                  opponent: 'GB',
                  opportunity: 0.68,
                  usageShare: 0.68,
                  softness: 'soft',
                  softnessScore: 1,
                  adjustedSoftness: 1,
                  gameScriptDelta: 0
                }
              ]
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        if (url.includes('/strength-of-schedule/tier2')) {
          const params = new URL(url, 'http://localhost').searchParams
          return new Response(
            JSON.stringify(
              buildTier2Payload({
                position: (params.get('position') ?? 'RB') as StrengthOfScheduleTier2Response['position']
              })
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
        if (url.includes('/strength-of-schedule/tier1/opportunity')) {
          const params = new URL(url, 'http://localhost').searchParams
          const position = params.get('position') ?? 'RB'
          const window = (params.get('window') ?? 'l8') as StrengthOfScheduleTier1Response['window']
          const leagueId = params.get('leagueId')
          return new Response(
            JSON.stringify({
              season: 2026,
              position,
              window,
              week: Number(params.get('week') ?? 10),
              ratedThroughWeek: 9,
              ratingWeeks: [2, 3, 4, 5, 6, 7, 8, 9],
              shrinkK: 4,
              fetchedAt: '2026-11-08T12:00:00Z',
              source: 'nflverse',
              stale: false,
              leagueId: leagueId ?? undefined,
              leagueName: leagueId ? 'Girls Who Ball' : undefined,
              joinStats: leagueId ? { matched: 1, unmatched: 0 } : undefined,
              players: [
                {
                  playerId: leagueId ? 9001 : null,
                  name: 'Workhorse',
                  team: 'CHI',
                  position: 'RB',
                  week: 10,
                  opponent: 'GB',
                  opponentRank: 3,
                  softness: 'soft',
                  softnessScore: 1,
                  usageShare: 0.72,
                  opportunity: 0.72,
                  joinStatus: leagueId ? 'matched' : undefined
                }
              ]
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }
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
    await waitFor(() => expect(screen.getByTestId('sos-opportunity-table')).toBeInTheDocument())
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(calls.some((url) => url.includes('/tier1/opportunity') && url.includes('window=l8'))).toBe(true)
  })

  it('refetches opportunity with leagueId when league is selected', async () => {
    localStorage.removeItem('workbook-league-id')
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-league-select')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('sos-league-select'), { target: { value: '1216398267' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('tier1/opportunity') && url.includes('leagueId=1216398267'))).toBe(
        true
      )
    })
    expect(screen.getByTestId('sos-opportunity-join-stats')).toHaveTextContent('matched 1')
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

  it('cross-links to Workbook with week in sessionStorage', async () => {
    const navigate = vi.fn()
    sessionStorage.clear()
    render(<WeekSosView onNavigateTab={navigate} />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('sos-workbook-cross-link'))

    expect(sessionStorage.getItem('crossLink.week')).toBe('10')
    expect(navigate).toHaveBeenCalledWith('week-workbook')
  })

  it('keeps tier2 fetches when position is WR', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('sos-view-mode'), { target: { value: 'tier2' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/strength-of-schedule/tier2?'))).toBe(true)
    })
    vi.mocked(fetch).mockClear()

    fireEvent.change(screen.getByTestId('sos-position'), { target: { value: 'WR' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/strength-of-schedule/tier2?') && url.includes('position=WR'))).toBe(
        true
      )
      expect(calls.some((url) => url.includes('/tier1?') && url.includes('position=WR'))).toBe(false)
    })
    expect(screen.getByTestId('sos-view-mode')).toHaveValue('tier2')
  })

  it('falls back to tier1 when DST is selected in tier2 mode', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('sos-view-mode'), { target: { value: 'tier2' } })
    await waitFor(() => expect(screen.getByTestId('sos-view-mode')).toHaveValue('tier2'))
    vi.mocked(fetch).mockClear()

    fireEvent.change(screen.getByTestId('sos-position'), { target: { value: 'DST' } })
    await waitFor(() => {
      expect(screen.getByTestId('sos-view-mode')).toHaveValue('tier1')
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/strength-of-schedule/tier1?') && url.includes('position=DST'))).toBe(
        true
      )
    })
  })

  it('loads tier2 grid and opportunity when tier2 view is selected', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('sos-view-mode'), { target: { value: 'tier2' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/strength-of-schedule/tier2?'))).toBe(true)
      expect(calls.some((url) => url.includes('/tier2/opportunity'))).toBe(true)
    })
    expect(screen.getByTestId('sos-source-line')).toHaveTextContent('epa_allowed')
  })

  it('applies position from sessionStorage on mount', async () => {
    sessionStorage.setItem('crossLink.position', 'WR')
    render(<WeekSosView />)
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('position=WR'))).toBe(true)
    })
    expect(sessionStorage.getItem('crossLink.position')).toBeNull()
  })

  it('sends wrRole=slot when Clay Slot WR toggle is selected', async () => {
    render(<WeekSosView />)
    await waitFor(() => expect(screen.getByTestId('sos-table')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('sos-position'), { target: { value: 'WR' } })
    await waitFor(() => expect(screen.getByTestId('sos-wr-role-slot')).toBeInTheDocument())
    vi.mocked(fetch).mockClear()
    fireEvent.click(screen.getByTestId('sos-wr-role-slot'))
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/tier1?') && url.includes('wrRole=slot'))).toBe(true)
      expect(calls.some((url) => url.includes('tier1/opportunity') && url.includes('wrRole=slot'))).toBe(true)
    })
  })
})
