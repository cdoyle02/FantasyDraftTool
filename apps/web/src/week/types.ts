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
