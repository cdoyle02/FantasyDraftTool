/** Provider-agnostic NFL week odds + D/ST stream rows from the API. */

export interface WeekOddsGame {
  homeTeam: string
  awayTeam: string
  commenceTime: string
  spread: number
  total: number
  favoriteTeam: string
  underdogTeam: string
  /** Implied points the favorite offense scores (= underdog D/ST points allowed). */
  favoriteImplied: number
  /** Implied points the underdog offense scores (= favorite D/ST points allowed). */
  underdogImplied: number
  dstPlayTeam: string
  bookmaker: string
}

export interface WeekOddsResponse {
  week: number
  windowStart: string
  windowEnd: string
  fetchedAt: string
  games: WeekOddsGame[]
}

export type WeekOddsSortKey =
  | 'underdogImplied'
  | 'favoriteImplied'
  | 'spread'
  | 'total'
  | 'commenceTime'
  | 'dstPlayTeam'

export interface EspnLeague {
  id: string
  name: string
}

export interface EspnLeaguesResponse {
  leagues: EspnLeague[]
}

export interface KyleDstRanking {
  rank: number
  team: string
  teamName: string
  opponent: string
  ecr: number | null
  vsEcr: string
}

export interface KyleDstRankingsResponse {
  week: number | null
  fetchedAt: string
  sourceUrl: string
  rankings: KyleDstRanking[]
}

export interface KyleDstAvailableRow extends KyleDstRanking {
  status: string
  percentOwned: number | null
}

export interface KyleDstAvailableResponse extends KyleDstRankingsResponse {
  leagueId: string
  leagueName: string
  available: KyleDstAvailableRow[]
}

export interface JaredKRanking {
  rank: number
  player: string
  team: string
  opponent: string
  ecr: number | null
  vsEcr: string
}

export interface JaredKRankingsResponse {
  week: number | null
  fetchedAt: string
  sourceUrl: string
  rankings: JaredKRanking[]
}

export interface JaredKAvailableRow extends JaredKRanking {
  status: string
  percentOwned: number | null
}

export interface JaredKAvailableResponse extends JaredKRankingsResponse {
  leagueId: string
  leagueName: string
  available: JaredKAvailableRow[]
}
