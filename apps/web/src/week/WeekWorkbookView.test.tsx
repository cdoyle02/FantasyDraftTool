import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WeekWorkbookView } from './WeekWorkbookView'
import type {
  WorkbookExplainResponse,
  WorkbookInjuriesResponse,
  WorkbookMatchupsResponse,
  WorkbookMatricesResponse,
  WorkbookOldlResponse,
  WorkbookPaceResponse,
  WorkbookPoolRankResponse,
  WorkbookTeamRow,
  WorkbookTopResponse
} from './types'

/** Mirrors `draft_api.workbook.service.ATTRIBUTION` (Clay Out/Slot roles). */
const MOCK_ATTRIBUTION =
  'Computed by FantasyDraftTool from nflverse + odds. Out/Slot roles from ESPN Mike Clay WR/CB cheat sheet (role-based); stats from nflverse. Methodology inspired by Majesstik/OWS Workbook; not their sheet.'

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
    attribution: MOCK_ATTRIBUTION,
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

function buildTopPayload(overrides: Partial<WorkbookTopResponse> = {}): WorkbookTopResponse {
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: MOCK_ATTRIBUTION,
    method: 'plays_share_proxy',
    teams: [
      { team: 'AAA', topPct: 58.3, method: 'plays_share_proxy', sampleGames: 1 },
      { team: 'BBB', topPct: 41.7, method: 'plays_share_proxy', sampleGames: 1 }
    ],
    ...overrides
  }
}

function buildPacePayload(overrides: Partial<WorkbookPaceResponse> = {}): WorkbookPaceResponse {
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: MOCK_ATTRIBUTION,
    teams: [
      { team: 'AAA', playsPerGame: 65.0, passRate: 0.55, runRate: 0.45 },
      { team: 'BBB', playsPerGame: 60.0, passRate: 0.5, runRate: 0.5 }
    ],
    ...overrides
  }
}

function buildInjuriesPayload(overrides: Partial<WorkbookInjuriesResponse> = {}): WorkbookInjuriesResponse {
  return {
    season: 2026,
    week: 10,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'espn',
    stale: false,
    warnings: [],
    injuries: [
      {
        playerId: 1001,
        name: 'Player Out',
        team: 'AAA',
        status: 'O',
        bodyPart: 'Knee',
        practice: 'DNP',
        gameStatus: null
      }
    ],
    ...overrides
  }
}

function buildPoolRankPayload(overrides: Partial<WorkbookPoolRankResponse> = {}): WorkbookPoolRankResponse {
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    scoring: 'half_ppr',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: MOCK_ATTRIBUTION,
    players: [
      {
        name: 'Player A',
        team: 'AAA',
        salary: 5000,
        position: 'WR',
        matchupTeam: 'AAA',
        opponent: 'BBB',
        netFpG: 12.0,
        tier: 'top',
        joinStatus: 'matched',
        value: 2.4
      }
    ],
    ...overrides
  }
}

function buildOldlPayload(overrides: Partial<WorkbookOldlResponse> = {}): WorkbookOldlResponse {
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: MOCK_ATTRIBUTION,
    disclaimer: 'OL/DL proxy from nflverse; not Football Outsiders.',
    teams: [
      {
        team: 'AAA',
        pressureRateAllowed: 0.25,
        sackRateAllowed: 0.05,
        epaPerDropbackAllowed: 0.1,
        rankPressure: 5
      }
    ],
    games: [
      {
        home: 'AAA',
        away: 'BBB',
        kickoff: null,
        rows: [
          {
            team: 'AAA',
            role: 'offense_ol',
            pressureRateAllowed: 0.2,
            sackRateAllowed: 0.04,
            epaPerDropbackAllowed: 0.05,
            rankPressure: 8
          },
          {
            team: 'BBB',
            role: 'defense_dl',
            pressureRateAllowed: 0.3,
            sackRateAllowed: 0.07,
            epaPerDropbackAllowed: 0.12,
            rankPressure: 3
          }
        ]
      }
    ],
    ...overrides
  }
}

function buildMatricesPayload(overrides: Partial<WorkbookMatricesResponse> = {}): WorkbookMatricesResponse {
  const cell = (value: number, tier: 'top' | 'mid' | 'bottom') => ({
    value,
    tier,
    tierColor: tier === 'top' ? 'green' : tier === 'bottom' ? 'red' : 'neutral'
  }) as const
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    scoring: 'ppr',
    group: 'wr',
    metric: 'fp_per_game',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: MOCK_ATTRIBUTION,
    teams: [
      { team: 'AAA', off: cell(12, 'top'), def: cell(10, 'mid'), net: cell(11, 'top') },
      { team: 'BBB', off: cell(9, 'bottom'), def: cell(11, 'top'), net: cell(8, 'bottom') }
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
    attribution: MOCK_ATTRIBUTION,
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
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const parsed = new URL(url, 'http://localhost')
        const params = parsed.searchParams

        if (parsed.pathname === '/api/v1/espn/leagues') {
          return new Response(
            JSON.stringify({
              leagues: [
                { id: '1216398267', name: 'Girls Who Ball' },
                { id: '999', name: 'Other' }
              ]
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          )
        }

        if (parsed.pathname === '/api/v1/nfl/workbook/matchups') {
          const leagueId = params.get('leagueId')
          return new Response(
            JSON.stringify(
              buildPayload({
                week: Number(params.get('week') ?? 10),
                window: (params.get('window') as WorkbookMatchupsResponse['window']) ?? 'l4',
                scoring: (params.get('scoring') as WorkbookMatchupsResponse['scoring']) ?? 'ppr',
                slate: (params.get('slate') as WorkbookMatchupsResponse['slate']) ?? 'main',
                ...(leagueId
                  ? {
                      highlights: [
                        {
                          playerId: 1,
                          displayName: 'Player A',
                          nflTeam: 'AAA',
                          matchupTeam: 'AAA',
                          opponent: 'BBB',
                          role: 'roster' as const,
                          rosterSlot: 'WR'
                        },
                        {
                          playerId: 2,
                          displayName: 'Player B',
                          nflTeam: 'AAA',
                          matchupTeam: 'AAA',
                          opponent: 'BBB',
                          role: 'free_agent' as const,
                          rosterSlot: null
                        }
                      ],
                      joinStats: { matched: 2, unmatched_team: 0, unmatched_name_only: 0 }
                    }
                  : {})
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

        if (parsed.pathname === '/api/v1/nfl/workbook/top') {
          return new Response(JSON.stringify(buildTopPayload()), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          })
        }

        if (parsed.pathname === '/api/v1/nfl/workbook/pace') {
          return new Response(JSON.stringify(buildPacePayload()), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          })
        }

        if (parsed.pathname === '/api/v1/nfl/workbook/injuries') {
          return new Response(JSON.stringify(buildInjuriesPayload()), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          })
        }

        if (parsed.pathname.startsWith('/api/v1/nfl/workbook/matrices/')) {
          const group = parsed.pathname.split('/').pop() ?? 'wr'
          return new Response(
            JSON.stringify(buildMatricesPayload({ group: group as WorkbookMatricesResponse['group'] })),
            {
              status: 200,
              headers: { 'Content-Type': 'application/json' }
            }
          )
        }

        if (parsed.pathname === '/api/v1/nfl/workbook/oldl') {
          return new Response(JSON.stringify(buildOldlPayload()), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          })
        }

        if (parsed.pathname === '/api/v1/nfl/workbook/pool/rank' && init?.method === 'POST') {
          return new Response(JSON.stringify(buildPoolRankPayload()), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          })
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
    const attribution = screen.getByTestId('workbook-attribution')
    expect(attribution).toHaveTextContent('Computed by FantasyDraftTool')
    expect(attribution).toHaveTextContent('Clay')
    expect(screen.queryByTestId('workbook-stale-banner')).not.toBeInTheDocument()
  })

  it('shows a stale banner when the API falls back to a snapshot', async () => {
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/espn/leagues')) {
        return new Response(JSON.stringify({ leagues: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        })
      }
      if (url.includes('/workbook/matchups')) {
        return new Response(JSON.stringify(buildPayload({ stale: true, source: 'snapshot' })), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        })
      }
      throw new Error(`Unexpected fetch: ${url}`)
    })
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

  it('loads ESPN leagues, refetches with leagueId, and shows highlight badges', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-league-select')).toBeInTheDocument())

    fireEvent.change(screen.getByTestId('workbook-league-select'), {
      target: { value: '1216398267' }
    })
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('leagueId=1216398267'))).toBe(true)
    })
    await waitFor(() => {
      expect(screen.getByTestId('workbook-highlight-badge-AAA')).toHaveTextContent('2')
    })
    expect(screen.getByTestId('workbook-highlight-badge-AAA')).toHaveAttribute(
      'title',
      expect.stringContaining('Player A')
    )
  })

  it('cross-links to SoS with position in sessionStorage', async () => {
    const navigate = vi.fn()
    sessionStorage.clear()
    render(<WeekWorkbookView onNavigateTab={navigate} />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('workbook-cell-AAA-qb'))
    fireEvent.click(screen.getByTestId('workbook-sos-cross-link'))

    expect(sessionStorage.getItem('crossLink.position')).toBe('QB')
    expect(navigate).toHaveBeenCalledWith('week-sos')
  })

  it('applies week from sessionStorage on mount', async () => {
    sessionStorage.setItem('crossLink.week', '12')
    render(<WeekWorkbookView />)
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
      expect(calls.some((url) => url.includes('/workbook/matchups') && url.includes('week=12'))).toBe(
        true
      )
    })
    expect(sessionStorage.getItem('crossLink.week')).toBeNull()
  })

  it('renders workbook sub-navigation', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-subnav')).toBeInTheDocument())
    expect(screen.getByTestId('workbook-subnav-matchups')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-subnav-top')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-subnav-pace')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-subnav-injuries')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-subnav-matrices')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-subnav-pool')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-subnav-oldl')).toBeInTheDocument()
  })

  it('loads TOP data when the TOP sub-tab is selected', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('workbook-subnav-top'))
    await waitFor(() => expect(screen.getByTestId('workbook-top-table')).toBeInTheDocument())
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(calls.some((url) => url.includes('/workbook/top'))).toBe(true)
    expect(screen.getByTestId('workbook-top-row-AAA')).toHaveTextContent('58.3')
  })

  it('loads pace data when the Pace sub-tab is selected', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('workbook-subnav-pace'))
    await waitFor(() => expect(screen.getByTestId('workbook-pace-table')).toBeInTheDocument())
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(calls.some((url) => url.includes('/workbook/pace'))).toBe(true)
    expect(screen.getByTestId('workbook-pace-row-AAA')).toHaveTextContent('65.0')
  })

  it('loads injuries when league is selected and Injuries tab is active', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-league-select')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('workbook-league-select'), {
      target: { value: '1216398267' }
    })
    fireEvent.click(screen.getByTestId('workbook-subnav-injuries'))
    await waitFor(() => expect(screen.getByTestId('workbook-injuries-table')).toBeInTheDocument())
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(
      calls.some((url) => url.includes('/workbook/injuries') && url.includes('leagueId=1216398267'))
    ).toBe(true)
    expect(screen.getByTestId('workbook-injury-1001')).toHaveTextContent('Player Out')
  })

  it('loads matrices when the Matrices sub-tab is selected', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('workbook-subnav-matrices'))
    await waitFor(() => expect(screen.getByTestId('workbook-matrices-table')).toBeInTheDocument())
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(calls.some((url) => url.includes('/workbook/matrices/wr'))).toBe(true)
    expect(screen.getByTestId('workbook-matrix-row-AAA')).toHaveTextContent('T')
    expect(screen.getByTestId('workbook-matrix-row-AAA')).toHaveTextContent('11.0')
  })

  it('shows pool paste UI on Pool sub-tab without loading matchups again', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())
    const before = vi.mocked(fetch).mock.calls.filter((call) => String(call[0]).includes('/workbook/matchups')).length
    fireEvent.click(screen.getByTestId('workbook-subnav-pool'))
    await waitFor(() => expect(screen.getByTestId('workbook-pool-panel')).toBeInTheDocument())
    const after = vi.mocked(fetch).mock.calls.filter((call) => String(call[0]).includes('/workbook/matchups')).length
    expect(after).toBe(before)
  })

  it('loads OL/DL proxy when the OL/DL sub-tab is selected', async () => {
    render(<WeekWorkbookView />)
    await waitFor(() => expect(screen.getByTestId('workbook-table')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('workbook-subnav-oldl'))
    await waitFor(() => expect(screen.getByTestId('workbook-oldl-table')).toBeInTheDocument())
    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(calls.some((url) => url.includes('/workbook/oldl'))).toBe(true)
    expect(screen.getByTestId('workbook-oldl-disclaimer')).toBeInTheDocument()
    expect(screen.getByTestId('workbook-oldl-row-AAA')).toHaveTextContent('OL proxy')
  })
})
