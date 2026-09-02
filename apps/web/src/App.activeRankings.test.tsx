import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { DvsRecommendationsHeading } from './App'
import { useDraftStore } from './store/draftStore'

describe('active rankings badge', () => {
  afterEach(() => {
    cleanup()
    useDraftStore.setState({ importIdentity: undefined })
  })

  it('shows imported scoring profile on the DVS panel heading', () => {
    useDraftStore.setState({
      importIdentity: {
        fingerprint: 'fp-test',
        season: 2026,
        asOfDate: '2026-08-31',
        rankingType: 'standard',
        scoringProfile: 'Two Flex Too Furious',
        leagueSize: 8,
        sourceCheatsheetId: 'sheet-a',
        sourceUrl: 'https://example.com',
        positionCounts: { QB: 1 }
      }
    })
    render(<DvsRecommendationsHeading />)
    expect(screen.getByTestId('active-rankings-badge')).toHaveTextContent('Active rankings: Two Flex Too Furious')
    expect(screen.getByTestId('active-rankings-badge')).toHaveAttribute('title', 'League size 8 · As of 2026-08-31')
  })

  it('shows default copy when no CSV import is active', () => {
    render(<DvsRecommendationsHeading />)
    expect(screen.queryByTestId('active-rankings-badge')).not.toBeInTheDocument()
    expect(screen.getByText('Top 10 for your roster · pick goes to on-clock team')).toBeInTheDocument()
  })
})
