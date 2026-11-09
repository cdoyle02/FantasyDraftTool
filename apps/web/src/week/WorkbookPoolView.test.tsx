import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkbookPoolView, WORKBOOK_POOL_CSV_STORAGE_KEY } from './WorkbookPoolView'
import type { WorkbookPoolRankResponse } from './types'
import type { WorkbookP2Controls } from './WeekWorkbookP2Tabs'

const fixtureDir = dirname(fileURLToPath(import.meta.url))
const SAMPLE_CSV = readFileSync(join(fixtureDir, 'fixtures', 'dk_salaries_sample.csv'), 'utf8')

const CONTROLS: WorkbookP2Controls = {
  week: 10,
  window: 'l4',
  customStart: 1,
  customEnd: 17,
  scoring: 'half_ppr'
}

function buildRankPayload(overrides: Partial<WorkbookPoolRankResponse> = {}): WorkbookPoolRankResponse {
  return {
    season: 2026,
    week: 10,
    window: 'l4',
    scoring: 'half_ppr',
    ratedThroughWeek: 9,
    fetchedAt: '2026-11-08T12:00:00Z',
    source: 'nflverse',
    stale: false,
    attribution: 'Computed by FantasyDraftTool',
    players: [
      {
        name: "Ja'Marr Chase",
        team: 'CIN',
        salary: 8200,
        position: 'WR',
        matchupTeam: 'CIN',
        opponent: 'PIT',
        netFpG: 14.2,
        tier: 'top',
        joinStatus: 'matched',
        value: 1.73
      },
      {
        name: 'Joe Burrow',
        team: 'CIN',
        salary: 7000,
        position: 'QB',
        matchupTeam: 'CIN',
        opponent: 'PIT',
        netFpG: 18.5,
        tier: 'top',
        joinStatus: 'matched',
        value: 2.64
      },
      {
        name: 'Unknown Guy',
        team: 'FA',
        salary: 3000,
        position: 'WR',
        matchupTeam: null,
        opponent: null,
        netFpG: null,
        tier: null,
        joinStatus: 'unmatched',
        value: null
      }
    ],
    ...overrides
  }
}

describe('WorkbookPoolView', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/workbook/pool/rank')) {
          const body = JSON.parse(String(init?.body ?? '{}')) as { players: unknown[] }
          expect(body.players?.length).toBeGreaterThan(0)
          return new Response(JSON.stringify(buildRankPayload()), {
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
    sessionStorage.clear()
  })

  it('parses pasted CSV, ranks on button click, and renders the table', async () => {
    render(<WorkbookPoolView controls={CONTROLS} />)
    fireEvent.change(screen.getByTestId('workbook-pool-csv-input'), { target: { value: SAMPLE_CSV } })

    await waitFor(() => {
      expect(screen.getByTestId('workbook-pool-parse-count')).toHaveTextContent('3 players')
    })

    fireEvent.click(screen.getByTestId('workbook-pool-rank-button'))

    await waitFor(() => {
      expect(screen.getByTestId('workbook-pool-table')).toBeInTheDocument()
    })

    expect(screen.getByTestId("workbook-pool-row-Ja'Marr-Chase")).toHaveTextContent('14.2')
    expect(screen.getByTestId('workbook-pool-row-Ja\'Marr-Chase')).toHaveTextContent('matched')
    expect(screen.getByTestId('workbook-pool-join-stats')).toHaveTextContent('1 unmatched')

    fireEvent.click(screen.getByTestId('workbook-pool-filter-unmatched'))
    expect(screen.queryByTestId("workbook-pool-row-Ja'Marr-Chase")).not.toBeInTheDocument()
    expect(screen.getByTestId('workbook-pool-row-Unknown-Guy')).toBeInTheDocument()

    const calls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]))
    expect(calls.some((path) => path.includes('/workbook/pool/rank'))).toBe(true)
  })

  it('persists CSV text in sessionStorage', async () => {
    render(<WorkbookPoolView controls={CONTROLS} />)
    fireEvent.change(screen.getByTestId('workbook-pool-csv-input'), { target: { value: SAMPLE_CSV } })
    await waitFor(() => {
      expect(sessionStorage.getItem(WORKBOOK_POOL_CSV_STORAGE_KEY)).toContain('Ja')
    })
  })
})
