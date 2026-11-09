import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekWorkbookView } from './WeekWorkbookView'
import type {
  WorkbookExplainResponse,
  WorkbookMatchupsResponse,
  WorkbookTeamRow
} from './types'

function buildRow(overrides: Partial<WorkbookTeamRow> = {}): WorkbookTeamRow {
  return {
    team: 'AAA',
    homeAway: 'home',
    opponent: 'BBB',
    gameEnvironment: {
      netDsr: 0.55,
      combNetDsr: 0.52,
      netDsrDiff: 0.03,
      netProe: 1.2,
      netPassPlays: 33,
      netEpaPass: 0.05,
      netXplsvPass: 0.1,
      netRunPlays: 25,
      netEpaRun: 0.02,
      netXplsvRun: 0.08,
      vegasImpliedPoints: 24.5
    },
    qb: { fpGTot: 18.2, fpGPass: 14.1, fpGRun: 4.1, ydsG: 265, passTdG: 1.8 },
    allWr: { fpG: 12.0, tarG: 7.1, tarPct: 0.22, ydG: 65, tdG: 0.4 },
    outWr: { fpG: null, reason: 'clay_unavailable' },
    slotWr: { fpG: null, reason: 'clay_unavailable' },
    te: { fpG: 8.5, tarG: 4.2, tarPct: 0.15, ydG: 40, tdG: 0.3 },
    rb: {
      fpGTot: 15.0,
      fpRec: 4.0,
      fpRun: 11.0,
      tarG: 2.5,
      tarPct: 0.09,
      recYdG: 18,
      recTdG: 0.1,
      attG: 14,
      rushYdG: 58,
      rushTdG: 0.5
    },
    ...overrides
  }
}

function buildPayload(overrides: Partial<WorkbookMatchupsResponse> = {}): WorkbookMatchupsResponse {
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    scoring: 'ppr',
    slate: 'main',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: 'Computed by FantasyDraftTool from nflverse + odds.',
    games: [
      {
        away: 'BBB',
        home: 'AAA',
        kickoff: '2026-11-09T18:00:00Z',
        mainSlate: true,
        rows: [
          buildRow(),
          buildRow({
            team: 'BBB',
            homeAway: 'away',
            opponent: 'AAA',
            gameEnvironment: {
              netDsr: 0.4,
              combNetDsr: 0.52,
              netDsrDiff: -0.03,
              netProe: -1.2,
              netPassPlays: 30,
              netEpaPass: -0.02,
              netXplsvPass: 0.05,
              netRunPlays: 22,
              netEpaRun: -0.01,
              netXplsvRun: 0.03,
              vegasImpliedPoints: 19.5
            },
            qb: { fpGTot: 14.0, fpGPass: 11.0, fpGRun: 3.0, ydsG: 210, passTdG: 1.1 },
            allWr: { fpG: 9.0, tarG: 6.0, tarPct: 0.18, ydG: 50, tdG: 0.2 },
            te: { fpG: 6.0, tarG: 3.0, tarPct: 0.1, ydG: 28, tdG: 0.1 },
            rb: {
              fpGTot: 11.0,
              fpRec: 2.0,
              fpRun: 9.0,
              tarG: 1.5,
              tarPct: 0.05,
              recYdG: 10,
              recTdG: 0.0,
              attG: 12,
              rushYdG: 45,
              rushTdG: 0.3
            }
          })
        ]
      }
    ],
    ...overrides
  }
}

function buildExplainPayload(overrides: Partial<WorkbookExplainResponse> = {}): WorkbookExplainResponse {
  return {
    season: 2026,
    week: 10,
    team: 'AAA',
    opponent: 'BBB',
    metric: 'qb_fp',
    window: 'l4',
    scoring: 'ppr',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: 'Computed by FantasyDraftTool from nflverse + odds.',
    off: 20.1,
    def: 16.3,
    net: 18.2,
    ...overrides
  }
}

describe('WeekWorkbookView', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const parsed = new URL(url, 'http://localhost')
        const params = parsed.searchParams

        if (parsed.pathname === '/api/v1/nfl/workbook/matchups') {
          return new Response(
            JSON.stringify(
              buildPayload({
                week: Number(params.get('week') ?? 10),
                window: (params.get('window') as WorkbookMatchupsResponse['window']) ?? 'l4',
                scoring: (params.get('scoring') as WorkbookMatchupsResponse['scoring']) ?? 'ppr',
                slate: (params.get('slate') as WorkbookMatchupsResponse['slate']) ?? 'main'
              })
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }

        if (parsed.pathname === '/api/v1/nfl/workbook/explain') {
          return new Response(
            JSON.stringify(
              buildExplainPayload({
                team: params.get('team') ?? 'AAA',
                metric: (params.get('metric') as WorkbookExplainResponse['metric']) ?? 'qb_fp'
              })
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }

        throw new Error(`Unexpected fetch: ${url}`)
      })
    )
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('loads the board with controls, team rows, and an attribution footer', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => {
      expect(screen.getByTestId('workbook-table')).toBeInTheDocument()
    })
    expect(screen.getByTestId('workbook-row-AAA')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-row-BBB')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-cell-AAA-vegas')).toHaveTextContent('24.5')
    expect(screen.getByTestId('workbook-attribution')).toHaveTextContent('Computed by FantasyDraftTool')
    expect(screen.queryByTestId('workbook-stale-banner')).not.toBeInTheDocument()
  })

  it('shows a stale banner when the API falls back to a snapshot', async () => {
    vi.mocked(fetch).mockImplementationOnce(async () =>
      new Response(JSON.stringify(buildPayload({ stale: true, source: 'snapshot' })), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    )
    render(<WeekWorkbookView />)
    await waitFor(() => {
      expect(screen.getByTestId('workbook-stale-banner')).toBeInTheDocument()
    })
  })

  it('refetches when switching week, window, scoring, or slate', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())

    fireEvent.change(screen.getByTestId('workbook-week'), { target: { value: '12' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/workbook/matchups') && url.includes('week=12'))).toBe(true)
    })

    fireEvent.click(screen.getByTestId('workbook-window-season'))
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('window=season'))).toBe(true)
    })

    fireEvent.change(screen.getByTestId('workbook-scoring'), { target: { value: 'half_ppr' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('scoring=half_ppr'))).toBe(true)
    })

    fireEvent.change(screen.getByTestId('workbook-slate'), { target: { value: 'all' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('slate=all'))).toBe(true)
    })

    fireEvent.click(screen.getByTestId('workbook-window-custom'))
    fireEvent.change(screen.getByTestId('workbook-start-week'), { target: { value: '3' } })
    fireEvent.change(screen.getByTestId('workbook-end-week'), { target: { value: '6' } })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(
        calls.some(
          (url) => url.includes('window=custom') && url.includes('startWeek=3') && url.includes('endWeek=6')
        )
      ).toBe(true)
    })
  })

  it('opens an explain panel with off/def/net when a clickable cell is selected', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('workbook-cell-AAA-qb'))

    await waitFor(() => {
      expect(screen.getByTestId('workbook-explain-panel')).toBeInTheDocument()
    })
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(
      calls.some((url) => url.includes('/workbook/explain') && url.includes('team=AAA') && url.includes('metric=qb_fp'))
    ).toBe(true)
    expect(screen.getByTestId('workbook-explain-panel')).toHaveTextContent('20.1')
    expect(screen.getByTestId('workbook-explain-panel')).toHaveTextContent('16.3')
    expect(screen.getByTestId('workbook-explain-panel')).toHaveTextContent('18.2')
  })
})
