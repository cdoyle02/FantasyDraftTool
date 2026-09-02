import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { ImportDialog } from './App'
import { buildFootballersCsv, leagueARows } from './data/footballersImport.fixtures'
import { useDraftStore } from './store/draftStore'
import { defaultLeague } from './types'

function csvFile(content: string, name = 'league-a.csv') {
  const file = new File([content], name, { type: 'text/csv' })
  Object.defineProperty(file, 'text', {
    value: async () => content
  })
  return file
}

const eightTeamNoKicker = {
  ...defaultLeague,
  teamCount: 8,
  rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 2, SUPERFLEX: 0, BENCH: 6, K: 0, DST: 1 }
}

describe('ImportDialog replace button', () => {
  beforeEach(() => {
    useDraftStore.setState({
      picks: [],
      keepers: [],
      adjustments: {},
      settings: eightTeamNoKicker,
      savedRankings: [],
      importIdentity: undefined,
      activeSavedProfileId: undefined
    })
  })

  afterEach(() => {
    cleanup()
  })

  it('shows Replace active rankings after a valid CSV is chosen', async () => {
    render(<ImportDialog close={() => undefined} />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [csvFile(buildFootballersCsv(leagueARows()))] } })

    await waitFor(() => {
      expect(screen.getByTestId('import-preflight')).toBeInTheDocument()
    })
    expect(screen.getAllByRole('button', { name: 'Replace active rankings' })).toHaveLength(1)
  })

  it('shows validation errors instead of Replace when league size mismatches', async () => {
    useDraftStore.setState({
      settings: {
        ...defaultLeague,
        teamCount: 12,
        rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPERFLEX: 0, BENCH: 6, K: 1, DST: 1 }
      }
    })
    render(<ImportDialog close={() => undefined} />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [csvFile(buildFootballersCsv(leagueARows()))] } })

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/league size/i)
    })
    expect(screen.queryByRole('button', { name: 'Replace active rankings' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Update League Setup to match this CSV/i })).toBeInTheDocument()
  })
})
