import { useEffect, useMemo, useState } from 'react'
import { draftApi } from '../api/client'
import type {
  EspnLeague,
  SosMetric,
  SosPosition,
  SosSoftness,
  SosTier1Window,
  StrengthOfScheduleResponse,
  StrengthOfScheduleTier1OpportunityResponse,
  StrengthOfScheduleTier1Response
} from './types'
import { WORKBOOK_LEAGUE_STORAGE_KEY } from './WeekWorkbookView'

/** sessionStorage — Workbook tab reads once on mount (`crossLink.week`). */
const CROSS_LINK_WEEK_KEY = 'crossLink.week'
/** sessionStorage — SoS tab reads once on mount (`crossLink.position`). */
const CROSS_LINK_POSITION_KEY = 'crossLink.position'

const POSITIONS: SosPosition[] = ['QB', 'RB', 'WR', 'TE', 'DST']

export type WeekShellTab = 'week-sos' | 'week-workbook'

export type WeekSosViewProps = {
  onNavigateTab?: (tab: WeekShellTab) => void
}
const WEEK_OPTIONS = Array.from({ length: 18 }, (_, i) => i + 1)
const RATING_WINDOWS: { key: SosTier1Window; label: string }[] = [
  { key: 'l4', label: 'L4' },
  { key: 'l8', label: 'L8' },
  { key: 'season', label: 'Season' }
]

type WindowPreset = 'ros' | 'playoffs' | 'full' | 'custom'
type SosViewMode = 'tier1' | 'classic'

function rankColor(rank: number | null): string {
  if (rank == null) return 'transparent'
  const t = Math.max(0, Math.min(1, (rank - 1) / 31))
  const hue = 120 * (1 - t)
  return `hsla(${hue}, 70%, 35%, 0.55)`
}

function softnessColor(softness: SosSoftness | null): string {
  if (softness === 'soft') return 'hsla(120, 70%, 32%, 0.62)'
  if (softness === 'tough') return 'hsla(0, 70%, 38%, 0.62)'
  if (softness === 'neutral') return 'hsla(48, 75%, 36%, 0.45)'
  return 'transparent'
}

function softnessBadge(softness: SosSoftness | null): string {
  if (softness === 'soft') return 'S'
  if (softness === 'tough') return 'T'
  if (softness === 'neutral') return 'N'
  return '—'
}

function formatAvg(value: number | null | undefined): string {
  if (typeof value !== 'number') return '—'
  return value.toFixed(1)
}

function formatShare(value: number | null | undefined): string {
  if (typeof value !== 'number') return '—'
  return `${(value * 100).toFixed(0)}%`
}

function formatOpportunity(value: number | null | undefined): string {
  if (typeof value !== 'number') return '—'
  return value.toFixed(3)
}

function presetWindow(
  preset: Exclude<WindowPreset, 'custom'>,
  ratedThroughWeek: number
): { startWeek: number; endWeek: number } {
  if (preset === 'playoffs') return { startWeek: 15, endWeek: 17 }
  if (preset === 'full') return { startWeek: 1, endWeek: 18 }
  const start = Math.max(1, Math.min(17, ratedThroughWeek + 1 || 1))
  return { startWeek: start, endWeek: 17 }
}

export function WeekSosView({ onNavigateTab }: WeekSosViewProps = {}) {
  const [position, setPosition] = useState<SosPosition>(() => {
    try {
      const linked = sessionStorage.getItem(CROSS_LINK_POSITION_KEY)
      if (linked && POSITIONS.includes(linked as SosPosition)) {
        sessionStorage.removeItem(CROSS_LINK_POSITION_KEY)
        return linked as SosPosition
      }
    } catch {
      // private mode
    }
    return 'RB'
  })
  const [viewMode, setViewMode] = useState<SosViewMode>('tier1')
  const [metric, setMetric] = useState<SosMetric>('fpa')
  const [ratingWindow, setRatingWindow] = useState<SosTier1Window>('l8')
  const [preset, setPreset] = useState<WindowPreset>('ros')
  const [customStart, setCustomStart] = useState(1)
  const [customEnd, setCustomEnd] = useState(17)
  const [classicData, setClassicData] = useState<StrengthOfScheduleResponse | null>(null)
  const [tier1Data, setTier1Data] = useState<StrengthOfScheduleTier1Response | null>(null)
  const [leagues, setLeagues] = useState<EspnLeague[]>([])
  const [leagueId, setLeagueId] = useState(() => {
    try {
      return localStorage.getItem(WORKBOOK_LEAGUE_STORAGE_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [opportunityData, setOpportunityData] = useState<StrengthOfScheduleTier1OpportunityResponse | null>(
    null
  )
  const [opportunityError, setOpportunityError] = useState('')
  const [opportunityLoading, setOpportunityLoading] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [ratedThrough, setRatedThrough] = useState(0)

  const window = useMemo(() => {
    if (preset === 'custom') {
      const start = Math.min(customStart, customEnd)
      const end = Math.max(customStart, customEnd)
      return { startWeek: start, endWeek: end }
    }
    return presetWindow(preset, ratedThrough)
  }, [preset, ratedThrough, customStart, customEnd])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        if (viewMode === 'tier1') {
          const payload = await draftApi.strengthOfScheduleTier1({
            position,
            window: ratingWindow,
            startWeek: window.startWeek,
            endWeek: window.endWeek
          })
          if (cancelled) return
          setTier1Data(payload)
          setClassicData(null)
          setRatedThrough(payload.ratedThroughWeek)
        } else {
          const payload = await draftApi.strengthOfSchedule({
            position,
            metric,
            startWeek: window.startWeek,
            endWeek: window.endWeek
          })
          if (cancelled) return
          setClassicData(payload)
          setTier1Data(null)
          setRatedThrough(payload.ratedThroughWeek)
        }
      } catch (err) {
        if (cancelled) return
        setClassicData(null)
        setTier1Data(null)
        setError(err instanceof Error ? err.message : 'Could not load strength of schedule.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [position, viewMode, metric, ratingWindow, window.startWeek, window.endWeek])

  useEffect(() => {
    let cancelled = false
    const loadLeagues = async () => {
      try {
        const payload = await draftApi.espnLeagues()
        if (cancelled) return
        const list = payload.leagues ?? []
        setLeagues(list)
        if (!leagueId && list[0]) {
          setLeagueId(list[0].id)
        }
      } catch {
        // opportunity table still loads nflverse rows without league list
      }
    }
    void loadLeagues()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    try {
      if (leagueId) localStorage.setItem(WORKBOOK_LEAGUE_STORAGE_KEY, leagueId)
    } catch {
      // private mode
    }
  }, [leagueId])

  const opportunityWeek = useMemo(
    () => Math.min(18, Math.max(1, (tier1Data?.ratedThroughWeek ?? ratedThrough) + 1 || 1)),
    [tier1Data?.ratedThroughWeek, ratedThrough]
  )

  useEffect(() => {
    if (viewMode !== 'tier1' || position === 'DST') {
      setOpportunityData(null)
      setOpportunityError('')
      return
    }
    let cancelled = false
    const loadOpportunity = async () => {
      setOpportunityLoading(true)
      setOpportunityError('')
      try {
        const payload = await draftApi.tier1Opportunity({
          position,
          window: ratingWindow,
          week: opportunityWeek,
          leagueId: leagueId || undefined
        })
        if (cancelled) return
        setOpportunityData(payload)
      } catch (err) {
        if (cancelled) return
        setOpportunityData(null)
        setOpportunityError(err instanceof Error ? err.message : 'Could not load opportunity scores.')
      } finally {
        if (!cancelled) setOpportunityLoading(false)
      }
    }
    void loadOpportunity()
    return () => {
      cancelled = true
    }
  }, [viewMode, position, ratingWindow, opportunityWeek, leagueId])

  const applyPreset = (next: Exclude<WindowPreset, 'custom'>) => {
    const resolved = presetWindow(next, ratedThrough)
    setCustomStart(resolved.startWeek)
    setCustomEnd(resolved.endWeek)
    setPreset(next)
  }

  const onCustomStart = (week: number) => {
    setCustomStart(week)
    setPreset('custom')
  }

  const onCustomEnd = (week: number) => {
    setCustomEnd(week)
    setPreset('custom')
  }

  const activeRatedThrough =
    viewMode === 'tier1' ? tier1Data?.ratedThroughWeek ?? 0 : classicData?.ratedThroughWeek ?? 0
  const activeStale = viewMode === 'tier1' ? tier1Data?.stale : classicData?.stale
  const activeSource = viewMode === 'tier1' ? tier1Data?.source : classicData?.source

  const metricLabel =
    viewMode === 'tier1'
      ? `Shrunk aFPA · ${ratingWindow.toUpperCase()} rating`
      : metric === 'fpa'
        ? 'Points allowed'
        : 'Schedule adjusted'
  const scoringNote = position === 'DST' ? 'ESPN-style D/ST scoring (nflverse team stats)' : 'Full PPR team totals (nflverse)'
  const sourceLine =
    activeRatedThrough > 0 || activeSource
      ? [
          scoringNote,
          activeRatedThrough > 0 ? `rated through week ${activeRatedThrough}` : 'no completed weeks yet',
          viewMode === 'tier1' && tier1Data ? `shrink k=${tier1Data.shrinkK}` : null,
          activeStale ? 'snapshot fallback' : activeSource
        ]
          .filter(Boolean)
          .join(' · ')
      : null

  const weekLabel =
    window.startWeek === window.endWeek
      ? `week ${window.startWeek}`
      : `weeks ${window.startWeek}–${window.endWeek}`

  const teamRows = viewMode === 'tier1' ? tier1Data?.teams ?? [] : classicData?.teams ?? []
  const opportunityPlayers = opportunityData?.players ?? []
  const rosterOverlay = Boolean(leagueId && opportunityData?.leagueId)

  return (
    <div className="space-y-4" data-testid="week-sos-view">
      <section className="mb-1 grid gap-3 rounded-2xl border border-line bg-gradient-to-r from-panel to-ink p-4 shadow-glow lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="eyebrow">Matchups</p>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">Strength of schedule</h2>
            <button
              type="button"
              data-testid="sos-workbook-cross-link"
              className="text-xs font-semibold text-mint hover:underline"
              onClick={() => {
                const nextWeek = Math.min(18, Math.max(1, activeRatedThrough + 1 || 10))
                try {
                  sessionStorage.setItem(CROSS_LINK_WEEK_KEY, String(nextWeek))
                } catch {
                  // private mode
                }
                onNavigateTab?.('week-workbook')
              }}
            >
              See this week&apos;s Net board
            </button>
          </div>
          <p className="mt-1 text-xs text-muted">
            Household grid ·{' '}
            {viewMode === 'tier1'
              ? 'S / N / T = soft / neutral / tough defensive buckets'
              : 'green = easy opponent rank · red = tough · not FootClan numbers'}
          </p>
          {sourceLine && (
            <p className="mt-1 text-[11px] text-muted" data-testid="sos-source-line">
              {sourceLine}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Position
            <select
              data-testid="sos-position"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={position}
              onChange={(event) => setPosition(event.target.value as SosPosition)}
            >
              {POSITIONS.map((pos) => (
                <option key={pos} value={pos}>
                  {pos}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            View
            <select
              data-testid="sos-view-mode"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={viewMode}
              onChange={(event) => setViewMode(event.target.value as SosViewMode)}
            >
              <option value="tier1">Tier 1 (shrunk aFPA)</option>
              <option value="classic">Classic (FPA / PAE)</option>
            </select>
          </label>
          {viewMode === 'classic' && (
            <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
              Metric
              <select
                data-testid="sos-metric"
                className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
                value={metric}
                onChange={(event) => setMetric(event.target.value as SosMetric)}
              >
                <option value="fpa">Points allowed</option>
                <option value="pae">Schedule adjusted</option>
              </select>
            </label>
          )}
          {viewMode === 'tier1' && (
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Rating window</span>
              <div className="flex flex-wrap rounded-lg border border-line p-0.5" role="group" aria-label="Tier1 rating window">
                {RATING_WINDOWS.map(({ key, label }) => (
                  <button
                    key={key}
                    type="button"
                    data-testid={`sos-rating-${key}`}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                      ratingWindow === key ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                    }`}
                    onClick={() => setRatingWindow(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Display window</span>
            <div className="flex flex-wrap rounded-lg border border-line p-0.5" role="group" aria-label="Week window">
              {(
                [
                  ['ros', 'Rest of season'],
                  ['playoffs', 'Playoffs'],
                  ['full', 'Full season']
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  data-testid={`sos-window-${key}`}
                  className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                    preset === key ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                  }`}
                  onClick={() => applyPreset(key)}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                data-testid="sos-window-custom"
                className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                  preset === 'custom' ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                }`}
                onClick={() => {
                  setCustomStart(window.startWeek)
                  setCustomEnd(window.endWeek)
                  setPreset('custom')
                }}
              >
                Custom
              </button>
            </div>
          </div>
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            From
            <select
              data-testid="sos-start-week"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={window.startWeek}
              onChange={(event) => onCustomStart(Number(event.target.value))}
            >
              {WEEK_OPTIONS.map((week) => (
                <option key={week} value={week}>
                  W{week}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            To
            <select
              data-testid="sos-end-week"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={window.endWeek}
              onChange={(event) => onCustomEnd(Number(event.target.value))}
            >
              {WEEK_OPTIONS.map((week) => (
                <option key={week} value={week}>
                  W{week}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-400/30 bg-rose-400/10 px-4 py-2 text-xs text-rose-100">
          {error}
        </div>
      )}

      <section className="panel overflow-hidden">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{metricLabel}</p>
            <h2>
              {position} · {weekLabel}
            </h2>
          </div>
          {loading && <p className="text-xs text-muted">Loading…</p>}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-xs" data-testid="sos-table">
            <thead>
              <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
                <th className="sticky left-0 z-10 bg-panel px-2 py-2">Rank</th>
                <th className="sticky left-10 z-10 bg-panel px-2 py-2">Team</th>
                <th className="px-2 py-2">Opp avg</th>
                {Array.from({ length: 18 }, (_, i) => i + 1).map((week) => (
                  <th key={week} className="px-1 py-2 text-center font-semibold">
                    W{week}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {teamRows.map((row) => (
                <tr key={row.team} className="border-b border-line/60" data-testid={`sos-row-${row.team}`}>
                  <td className="sticky left-0 z-10 bg-panel px-2 py-1.5 font-semibold text-mint">{row.rank}</td>
                  <td className="sticky left-10 z-10 bg-panel px-2 py-1.5 font-bold">{row.team}</td>
                  <td className="px-2 py-1.5 tabular-nums text-muted">{formatAvg(row.opponentAverage)}</td>
                  {row.weeks.map((cell) => {
                    if (cell.bye) {
                      return (
                        <td
                          key={cell.week}
                          data-testid={`sos-cell-${row.team}-${cell.week}`}
                          className={`px-1 py-1.5 text-center text-muted ${cell.inWindow ? '' : 'opacity-40'}`}
                        >
                          —
                        </td>
                      )
                    }
                    if (viewMode === 'tier1' && 'softness' in cell) {
                      const tier1Cell = cell as (typeof row.weeks)[number] & {
                        shrunkAfpa?: number | null
                        rank?: number | null
                        softness?: SosSoftness | null
                      }
                      const oppRank = tier1Cell.rank ?? null
                      const softness = tier1Cell.softness ?? null
                      return (
                        <td
                          key={cell.week}
                          data-testid={`sos-cell-${row.team}-${cell.week}`}
                          className={`px-1 py-1 text-center ${cell.inWindow ? '' : 'opacity-40'}`}
                          style={{ backgroundColor: softnessColor(softness) }}
                          title={
                            cell.opponent
                              ? `${cell.opponent} · rank ${oppRank ?? '—'} · ${formatAvg(tier1Cell.shrunkAfpa)} aFPA · ${softness ?? '—'}`
                              : undefined
                          }
                        >
                          <div
                            className="text-[9px] font-bold uppercase tracking-wide leading-tight text-slate-100"
                            data-testid={`sos-badge-${row.team}-${cell.week}`}
                          >
                            {softnessBadge(softness)}
                          </div>
                          <div className="font-bold tabular-nums leading-tight">{oppRank ?? '—'}</div>
                          <div className="text-[10px] font-semibold leading-tight text-slate-200/90">
                            {cell.opponent}
                          </div>
                        </td>
                      )
                    }
                    const classicCell = cell as {
                      opponentRank: number | null
                      opponentValue: number | null
                    }
                    return (
                      <td
                        key={cell.week}
                        data-testid={`sos-cell-${row.team}-${cell.week}`}
                        className={`px-1 py-1 text-center ${cell.inWindow ? '' : 'opacity-40'}`}
                        style={{ backgroundColor: rankColor(classicCell.opponentRank) }}
                        title={
                          cell.opponent
                            ? `${cell.opponent} · rank ${classicCell.opponentRank ?? '—'} · ${formatAvg(classicCell.opponentValue)}`
                            : undefined
                        }
                      >
                        <div className="font-bold tabular-nums leading-tight">
                          {classicCell.opponentRank ?? '—'}
                        </div>
                        <div className="text-[10px] font-semibold leading-tight text-slate-200/90">
                          {cell.opponent}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
              {!loading && !error && teamRows.length === 0 && (
                <tr>
                  <td colSpan={21} className="px-4 py-6 text-center text-muted">
                    No schedule data yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {viewMode === 'tier1' && position !== 'DST' && (
        <section className="panel overflow-hidden" data-testid="sos-opportunity-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Tier 1 opportunity</p>
              <h2>
                {position} · week {opportunityWeek} · softness × usage
              </h2>
              <p className="mt-1 text-[11px] text-muted">
                {rosterOverlay
                  ? `ESPN roster overlay · ${opportunityData?.leagueName ?? leagueId}`
                  : 'nflverse usage pool — pick a league to filter to your roster'}
              </p>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
                League (optional)
                <select
                  data-testid="sos-league-select"
                  className="min-w-[12rem] rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
                  value={leagueId}
                  onChange={(event) => setLeagueId(event.target.value)}
                >
                  <option value="">All nflverse {position}s</option>
                  {leagues.map((league) => (
                    <option key={league.id} value={league.id}>
                      {league.name}
                    </option>
                  ))}
                </select>
              </label>
              {opportunityLoading && <p className="text-xs text-muted">Loading…</p>}
            </div>
          </div>
          {opportunityError && (
            <div
              role="alert"
              className="mx-4 mb-2 rounded-lg border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs text-rose-100"
            >
              {opportunityError}
            </div>
          )}
          {opportunityData?.overlayError && leagueId && (
            <p className="px-4 pb-2 text-xs text-amber-200/90" data-testid="sos-opportunity-overlay-error">
              ESPN roster unavailable — showing an empty overlay ({opportunityData.overlayError}).
            </p>
          )}
          {rosterOverlay && opportunityData?.joinStats && (
            <p className="px-4 pb-2 text-[11px] text-muted" data-testid="sos-opportunity-join-stats">
              matched {opportunityData.joinStats.matched} · unmatched {opportunityData.joinStats.unmatched}
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-xs" data-testid="sos-opportunity-table">
              <thead>
                <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
                  <th className="px-3 py-2">#</th>
                  <th className="px-3 py-2">Player</th>
                  <th className="px-3 py-2">Team</th>
                  <th className="px-3 py-2">Opp</th>
                  <th className="px-3 py-2">Soft</th>
                  <th className="px-3 py-2">Usage</th>
                  <th className="px-3 py-2">Opp score</th>
                  {rosterOverlay && <th className="px-3 py-2">Join</th>}
                </tr>
              </thead>
              <tbody>
                {opportunityPlayers.map((row, index) => (
                  <tr key={`${row.playerId ?? row.name}-${index}`} className="border-b border-line/60">
                    <td className="px-3 py-1.5 tabular-nums text-muted">{index + 1}</td>
                    <td className="px-3 py-1.5 font-semibold">{row.name}</td>
                    <td className="px-3 py-1.5">{row.team}</td>
                    <td className="px-3 py-1.5">
                      {row.bye ? 'BYE' : row.opponent ?? '—'}
                    </td>
                    <td className="px-3 py-1.5 uppercase">{softnessBadge(row.softness)}</td>
                    <td className="px-3 py-1.5 tabular-nums">{formatShare(row.usageShare)}</td>
                    <td className="px-3 py-1.5 tabular-nums font-semibold text-mint">
                      {formatOpportunity(row.opportunity)}
                    </td>
                    {rosterOverlay && (
                      <td className="px-3 py-1.5 text-[10px] uppercase text-muted">{row.joinStatus ?? '—'}</td>
                    )}
                  </tr>
                ))}
                {!opportunityLoading && opportunityPlayers.length === 0 && (
                  <tr>
                    <td colSpan={rosterOverlay ? 8 : 7} className="px-4 py-6 text-center text-muted">
                      No opportunity rows yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
