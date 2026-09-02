import type { FootballersRankingDataset } from './footballersImport'

export function normalizeProfileName(name: string): string {
  return name.trim().toLowerCase()
}

export interface SavedRankingProfile {
  id: string
  displayName: string
  normalizedName: string
  dataset: FootballersRankingDataset
  createdAt: number
  updatedAt: number
}

export interface SavedRankingSummary {
  id: string
  displayName: string
  fingerprint: string
  scoringProfile: string
  leagueSize: number
  asOfDate: string
  playerCount: number
  updatedAt: number
}

export function summarizeSavedRanking(profile: SavedRankingProfile): SavedRankingSummary {
  return {
    id: profile.id,
    displayName: profile.displayName,
    fingerprint: profile.dataset.identity.fingerprint,
    scoringProfile: profile.dataset.identity.scoringProfile,
    leagueSize: profile.dataset.identity.leagueSize,
    asOfDate: profile.dataset.identity.asOfDate,
    playerCount: profile.dataset.rows.length,
    updatedAt: profile.updatedAt
  }
}
