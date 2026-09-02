import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { DvsRecommendationsHeading } from './App'
import { useDraftStore } from './store/draftStore'

describe('active rankings badge', () => {
  afterEach(() => {
    cleanup()
    useDraftStore.setState({
      importIdentity: undefined,
      activeSavedProfileId: undefined,
      savedRankings: []
    })
  })

  it('shows saved profile name on the DVS panel heading when present', () => {
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
        positionCounts: { QB: 1 },
        savedProfileName: 'Sunday League'
      }
    })
    render(<DvsRecommendationsHeading />)
    expect(screen.getByTestId('active-rankings-badge')).toHaveTextContent('Active rankings: Sunday League')
  })

  it('falls back to the active saved-profile summary when importIdentity lacks a display name', () => {
    useDraftStore.setState({
      activeSavedProfileId: 'profile-1',
      savedRankings: [{
        id: 'profile-1',
        displayName: 'Sunday League',
        fingerprint: 'fp-test',
        scoringProfile: 'Two Flex Too Furious',
        leagueSize: 8,
        asOfDate: '2026-08-31',
        playerCount: 2,
        updatedAt: 1
      }],
      importIdentity: {
        fingerprint: 'fp-test',
        season: 2026,
        asOfDate: '2026-08-31',
        rankingType: 'standard',
        scoringProfile: 'Two Flex Too Furious',
        leagueSize: 8,
        sourceCheatsheetId: 'sheet-a',
        positionCounts: { QB: 1 },
        savedProfileId: 'profile-1'
      }
    })
    render(<DvsRecommendationsHeading />)
    expect(screen.getByTestId('active-rankings-badge')).toHaveTextContent('Active rankings: Sunday League')
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
    expect(screen.getByTestId('active-rankings-badge')).toHaveAttribute('title', 'Two Flex Too Furious · League size 8 · As of 2026-08-31')
  })

  it('shows default copy when no CSV import is active', () => {
    render(<DvsRecommendationsHeading />)
    expect(screen.queryByTestId('active-rankings-badge')).not.toBeInTheDocument()
    expect(screen.getByText('Top 10 for your roster · pick goes to on-clock team')).toBeInTheDocument()
  })
})
