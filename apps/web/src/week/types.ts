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

export type SosPosition = 'QB' | 'RB' | 'WR' | 'TE' | 'DST'
export type SosMetric = 'fpa' | 'pae'

export interface SosWeekCell {
  week: number
  opponent: string | null
  opponentRank: number | null
  opponentValue: number | null
  bye: boolean
  inWindow: boolean
}

export interface SosTeamRow {
  team: string
  rank: number
  opponentAverage: number | null
  weeks: SosWeekCell[]
}

export interface StrengthOfScheduleResponse {
  season: number
  position: SosPosition
  metric: SosMetric
  startWeek: number
  endWeek: number
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  teams: SosTeamRow[]
}

export interface StrengthOfScheduleQuery {
  position: SosPosition
  metric: SosMetric
  startWeek?: number
  endWeek?: number
  season?: number
}

export type SosTier1Window = 'l4' | 'l8' | 'season'
export type SosSoftness = 'soft' | 'neutral' | 'tough'

export interface SosTier1WeekCell {
  week: number
  opponent: string | null
  shrunkAfpa: number | null
  rank: number | null
  softness: SosSoftness | null
  softnessScore: number | null
  bye: boolean
  inWindow: boolean
}

export interface SosTier1TeamRow {
  team: string
  rank: number
  opponentAverage: number | null
  weeks: SosTier1WeekCell[]
}

export interface StrengthOfScheduleTier1Response {
  season: number
  position: SosPosition
  window: SosTier1Window
  startWeek: number
  endWeek: number
  ratedThroughWeek: number
  ratingWeeks: number[]
  shrinkK: number
  fetchedAt: string
  source: string
  stale: boolean
  teams: SosTier1TeamRow[]
}

export interface StrengthOfScheduleTier1Query {
  position: SosPosition
  window?: SosTier1Window
  startWeek?: number
  endWeek?: number
  season?: number
}

export type Tier1JoinStatus = 'matched' | 'unmatched'

export interface Tier1OpportunityPlayer {
  playerId: number | null
  name: string
  team: string
  position: SosPosition
  week: number
  opponent: string | null
  opponentRank: number | null
  softness: SosSoftness | null
  softnessScore: number | null
  usageShare: number | null
  opportunity: number | null
  bye?: boolean
  joinStatus?: Tier1JoinStatus
  lineupSlot?: string | null
  injuryStatus?: string | null
  espnTeamId?: number | null
}

export interface StrengthOfScheduleTier1OpportunityResponse {
  season: number
  position: SosPosition
  window: SosTier1Window
  week: number
  ratedThroughWeek: number
  ratingWeeks: number[]
  shrinkK: number
  fetchedAt: string
  source: string
  stale: boolean
  players: Tier1OpportunityPlayer[]
  leagueId?: string
  leagueName?: string
  joinStats?: { matched: number; unmatched: number; skippedPosition?: number }
  overlayError?: string
}

export interface StrengthOfScheduleTier1OpportunityQuery {
  position: SosPosition
  window?: SosTier1Window
  week?: number
  season?: number
  leagueId?: string
}

export type SosTier2Position = 'QB' | 'RB' | 'WR' | 'TE'

export interface SosTier2WeekCell {
  week: number
  opponent: string | null
  shrunkEpa: number | null
  rank: number | null
  softness: SosSoftness | null
  softnessScore: number | null
  bye: boolean
  inWindow: boolean
}

export interface SosTier2TeamRow {
  team: string
  rank: number
  opponentAverage: number | null
  weeks: SosTier2WeekCell[]
}

export interface StrengthOfScheduleTier2Response {
  season: number
  position: SosTier2Position
  window: SosTier1Window
  startWeek: number
  endWeek: number
  ratedThroughWeek: number
  ratingWeeks: number[]
  shrinkK: number
  softnessMetric: string
  fetchedAt: string
  source: string
  stale: boolean
  teams: SosTier2TeamRow[]
}

export interface StrengthOfScheduleTier2Query {
  position: SosTier2Position
  window?: SosTier1Window
  startWeek?: number
  endWeek?: number
  season?: number
}

export interface Tier2OpportunityPlayer extends Tier1OpportunityPlayer {
  gameScriptDelta?: number
  adjustedSoftness?: number | null
  minOffenseSnapPct?: number
}

export interface StrengthOfScheduleTier2OpportunityResponse {
  season: number
  position: SosTier2Position
  window: SosTier1Window
  week: number
  ratedThroughWeek: number
  ratingWeeks: number[]
  shrinkK: number
  softnessMetric: string
  minOffenseSnapPct: number
  snapFiltered: boolean
  gameScriptApplied: boolean
  fetchedAt: string
  source: string
  stale: boolean
  players: Tier2OpportunityPlayer[]
  leagueId?: string
  leagueName?: string
  joinStats?: { matched: number; unmatched: number; skippedPosition?: number }
  overlayError?: string
  usageUnavailable?: boolean
}

export interface StrengthOfScheduleTier2OpportunityQuery {
  position: SosTier2Position
  window?: SosTier1Window
  week?: number
  season?: number
  leagueId?: string
}

/** Workbook Net Matchups — see `apps/api/src/draft_api/workbook/README.md` (SSOT for the math). */

export type WorkbookWindow = 'l4' | 'season' | 'custom'
export type WorkbookScoring = 'ppr' | 'half_ppr'
export type WorkbookSlate = 'main' | 'all'
export type WorkbookExplainMetric =
  | 'dsr'
  | 'qb_fp'
  | 'wr_fp'
  | 'te_fp'
  | 'rb_fp'
  | 'out_wr_fp'
  | 'slot_wr_fp'
export type WorkbookFeederGroup = 'dsr' | 'qb' | 'wr' | 'te' | 'rb' | 'targets' | 'yards' | 'tds'

export interface WorkbookGameEnvironment {
  netDsr: number | null
  combNetDsr: number | null
  netDsrDiff: number | null
  netProe: number | null
  netPassPlays: number | null
  netEpaPass: number | null
  netXplsvPass: number | null
  netRunPlays: number | null
  netEpaRun: number | null
  netXplsvRun: number | null
  vegasImpliedPoints: number | null
}

/** One OFF/DEF-netted positional block (QB / ALL WR / Out WR / Slot WR / TE / RB). Keys vary
 * per group (see README); `reason` is set instead of metrics when Out/Slot sample is too thin. */
export interface WorkbookPositionalBlock {
  [metric: string]: number | string | null | undefined
  reason?: string
}

export interface WorkbookTeamRow {
  team: string
  homeAway: 'home' | 'away'
  opponent: string
  gameEnvironment: WorkbookGameEnvironment
  qb: WorkbookPositionalBlock
  allWr: WorkbookPositionalBlock
  outWr: WorkbookPositionalBlock
  slotWr: WorkbookPositionalBlock
  te: WorkbookPositionalBlock
  rb: WorkbookPositionalBlock
}

export interface WorkbookGame {
  away: string
  home: string
  kickoff: string | null
  mainSlate: boolean
  rows: WorkbookTeamRow[]
}

export type WorkbookHighlightRole = 'roster' | 'free_agent' | 'waiver'

export interface WorkbookHighlight {
  playerId: number
  displayName: string
  nflTeam: string
  matchupTeam: string
  opponent: string
  role: WorkbookHighlightRole
  rosterSlot: string | null
}

export interface WorkbookJoinStats {
  matched: number
  unmatched_team: number
  unmatched_name_only: number
}

export interface WorkbookMatchupsResponse {
  season: number
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  slate: WorkbookSlate
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  games: WorkbookGame[]
  highlights?: WorkbookHighlight[]
  joinStats?: WorkbookJoinStats
  overlayError?: string
}

export interface WorkbookMatchupsQuery {
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  slate: WorkbookSlate
  startWeek?: number
  endWeek?: number
  season?: number
  leagueId?: string
  ownerTeamId?: number
  includeFa?: boolean
}

export interface WorkbookFeederRow {
  team: string
  off: number | null
  def: number | null
  net: number | null
}

export interface WorkbookFeederResponse {
  season: number
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  group: WorkbookFeederGroup
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  teams: WorkbookFeederRow[]
}

export interface WorkbookFeederQuery {
  group: WorkbookFeederGroup
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  startWeek?: number
  endWeek?: number
  season?: number
}

export interface WorkbookExplainResponse {
  season: number
  week: number
  team: string
  opponent: string | null
  metric: WorkbookExplainMetric
  window: WorkbookWindow
  scoring: WorkbookScoring
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  off: number | null
  def: number | null
  net: number | null
}

export interface WorkbookExplainQuery {
  team: string
  week: number
  metric: WorkbookExplainMetric
  window: WorkbookWindow
  scoring: WorkbookScoring
  startWeek?: number
  endWeek?: number
  season?: number
}

/** Shared window params for Workbook P2 tab APIs (TOP, Pace, Matrices). */
export interface WorkbookP2WindowQuery {
  week: number
  window: WorkbookWindow
  startWeek?: number
  endWeek?: number
  season?: number
}

export type WorkbookTopMethod = 'pbp_drive' | 'plays_share_proxy'

export interface WorkbookTopTeamRow {
  team: string
  topPct: number | null
  method: WorkbookTopMethod
  sampleGames: number
}

export interface WorkbookTopResponse {
  season: number
  week: number
  window: WorkbookWindow
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  method: WorkbookTopMethod
  teams: WorkbookTopTeamRow[]
}

export interface WorkbookPaceTeamRow {
  team: string
  playsPerGame: number | null
  passRate: number | null
  runRate: number | null
}

export interface WorkbookPaceResponse {
  season: number
  week: number
  window: WorkbookWindow
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  teams: WorkbookPaceTeamRow[]
}

export interface WorkbookInjuryRow {
  playerId: number
  name: string
  team: string
  status: string
  bodyPart: string | null
  practice: string | null
  gameStatus: string | null
}

export interface WorkbookInjuriesResponse {
  season: number
  week: number
  fetchedAt: string
  source: string
  stale: boolean
  injuries: WorkbookInjuryRow[]
  warnings: string[]
}

export interface WorkbookInjuriesQuery {
  week: number
  leagueId: string
  season?: number
}

export type WorkbookMatrixGroup = 'qb' | 'wr' | 'te' | 'rb' | 'dsr'
export type WorkbookMatrixMetric =
  | 'fp_per_game'
  | 'targets_per_game'
  | 'yards_per_game'
  | 'tds_per_game'
  | 'dsr'
export type WorkbookMatrixTertile = 'top' | 'mid' | 'bottom'
export type WorkbookMatrixTierColor = 'green' | 'neutral' | 'red'

export interface WorkbookMatrixCell {
  value: number | null
  tier: WorkbookMatrixTertile | null
  tierColor: WorkbookMatrixTierColor | null
}

export interface WorkbookMatrixTeamRow {
  team: string
  off: WorkbookMatrixCell
  def: WorkbookMatrixCell
  net: WorkbookMatrixCell
}

export interface WorkbookMatricesResponse {
  season: number
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  group: WorkbookMatrixGroup
  metric: WorkbookMatrixMetric
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  teams: WorkbookMatrixTeamRow[]
}

export interface WorkbookMatricesQuery extends WorkbookP2WindowQuery {
  group: WorkbookMatrixGroup
  metric: WorkbookMatrixMetric
  scoring: WorkbookScoring
}

export type WorkbookSubTab =
  | 'matchups'
  | 'top'
  | 'pace'
  | 'injuries'
  | 'matrices'
  | 'pool'
  | 'oldl'

export type WorkbookPoolJoinStatus = 'matched' | 'unmatched'

export interface WorkbookPoolPlayerPayload {
  name: string
  team: string
  salary: number
  position: string
  opponent?: string
}

export interface WorkbookPoolRankRow {
  name: string
  team: string
  salary: number
  position: string
  matchupTeam: string | null
  opponent: string | null
  netFpG: number | null
  tier: WorkbookMatrixTertile | null
  joinStatus: WorkbookPoolJoinStatus
  value: number | null
}

export interface WorkbookPoolRankResponse {
  season: number
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  players: WorkbookPoolRankRow[]
}

export interface WorkbookPoolRankQuery {
  week: number
  window: WorkbookWindow
  scoring?: WorkbookScoring
  players: WorkbookPoolPlayerPayload[]
  startWeek?: number
  endWeek?: number
  season?: number
}

export type WorkbookOldlRole = 'offense_ol' | 'defense_dl'

export interface WorkbookOldlMetricRow {
  team: string
  role: WorkbookOldlRole
  pressureRateAllowed: number | null
  sackRateAllowed: number | null
  epaPerDropbackAllowed: number | null
  rankPressure: number | null
}

export interface WorkbookOldlTeamRow {
  team: string
  pressureRateAllowed: number | null
  sackRateAllowed: number | null
  epaPerDropbackAllowed: number | null
  rankPressure: number | null
}

export interface WorkbookOldlGame {
  home: string
  away: string
  kickoff: string | null
  rows: WorkbookOldlMetricRow[]
}

export interface WorkbookOldlResponse {
  season: number
  week: number
  window: WorkbookWindow
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  disclaimer: string
  teams: WorkbookOldlTeamRow[]
  games: WorkbookOldlGame[]
}
