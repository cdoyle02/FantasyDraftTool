import { Fragment, useEffect, useMemo, useState } from 'react'
import { ApiTokenPrompt } from '../api/ApiTokenPrompt'
import { draftApi, isApiAuthError } from '../api/client'
import {
  WorkbookClayShadowPanel,
  WorkbookFeedersPanel,
  WorkbookInjuriesPanel,
  WorkbookMatricesPanel,
  WorkbookPacePanel,
  WorkbookSubNav,
  WorkbookTopPanel
} from './WeekWorkbookP2Tabs'
import { WorkbookOldlPanel } from './WeekWorkbookP3Tabs'
import { WorkbookPoolView } from './WorkbookPoolView'
import type {
  EspnLeague,
  SosPosition,
  WorkbookExplainMetric,
  WorkbookExplainResponse,
  WorkbookHighlight,
  WorkbookMatchupsResponse,
  WorkbookScoring,
  WorkbookSlate,
  WorkbookSubTab,
  WorkbookTeamRow,
  WorkbookWindow
} from './types'

const WEEK_OPTIONS = Array.from({ length: 18 }, (_, i) => i + 1)
/** Persisted ESPN league for highlight overlay (Week D/ST pattern). */
export const WORKBOOK_LEAGUE_STORAGE_KEY = 'workbook-league-id'
/** sessionStorage — SoS tab reads once on mount (`crossLink.position`). */
const CROSS_LINK_POSITION_KEY = 'crossLink.position'
/** sessionStorage — Workbook tab reads once on mount (`crossLink.week`). */
const CROSS_LINK_WEEK_KEY = 'crossLink.week'

export type WeekShellTab = 'week-sos' | 'week-workbook'

export type WeekWorkbookViewProps = {
  onNavigateTab?: (tab: WeekShellTab) => void
}

function sosPositionForMetric(metric: WorkbookExplainMetric): SosPosition {
  switch (metric) {
    case 'qb_fp':
      return 'QB'
    case 'rb_fp':
      return 'RB'
    case 'wr_fp':
    case 'out_wr_fp':
    case 'slot_wr_fp':
      return 'WR'
    case 'te_fp':
      return 'TE'
    default:
      return 'RB'
  }
}

function highlightTooltip(players: WorkbookHighlight[]): string {
  return players.map((p) => `${p.displayName} (${p.role.replace('_', ' ')})`).join(', ')
}

/** Headline board columns. `explainMetric` is set when the `/workbook/explain`
 * endpoint can reconcile this cell (game-environment Comb/Diff have no single
 * team leg to explain, so they stay display-only — see `workbook/README.md`). */
interface Column {
  key: string
  label: string
  explainMetric?: WorkbookExplainMetric
  decimals: number
  getValue: (row: WorkbookTeamRow) => number | null
  getReason?: (row: WorkbookTeamRow) => string | undefined
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

const COLUMNS: Column[] = [
  { key: 'vegas', label: 'Vegas Impl', decimals: 1, getValue: (row) => row.gameEnvironment.vegasImpliedPoints },
  {
    key: 'netDsr',
    label: 'Net DSR',
    explainMetric: 'dsr',
    decimals: 3,
    getValue: (row) => row.gameEnvironment.netDsr
  },
  { key: 'combDsr', label: 'Comb DSR', decimals: 3, getValue: (row) => row.gameEnvironment.combNetDsr },
  { key: 'dsrDiff', label: 'DSR Diff', decimals: 3, getValue: (row) => row.gameEnvironment.netDsrDiff },
  {
    key: 'qb',
    label: 'QB',
    explainMetric: 'qb_fp',
    decimals: 1,
    getValue: (row) => asNumber(row.qb.fpGTot)
  },
  {
    key: 'allWr',
    label: 'ALL WR',
    explainMetric: 'wr_fp',
    decimals: 1,
    getValue: (row) => asNumber(row.allWr.fpG)
  },
  {
    key: 'outWr',
    label: 'Out WR',
    explainMetric: 'out_wr_fp',
    decimals: 1,
    getValue: (row) => asNumber(row.outWr.fpG),
    getReason: (row) => (typeof row.outWr.reason === 'string' ? row.outWr.reason : undefined)
  },
  {
    key: 'slotWr',
    label: 'Slot WR',
    explainMetric: 'slot_wr_fp',
    decimals: 1,
    getValue: (row) => asNumber(row.slotWr.fpG),
    getReason: (row) => (typeof row.slotWr.reason === 'string' ? row.slotWr.reason : undefined)
  },
  {
    key: 'te',
    label: 'TE',
    explainMetric: 'te_fp',
    decimals: 1,
    getValue: (row) => asNumber(row.te.fpG)
  },
  {
    key: 'rb',
    label: 'RB',
    explainMetric: 'rb_fp',
    decimals: 1,
    getValue: (row) => asNumber(row.rb.fpGTot)
  }
]

/** Color a cell by its percentile rank within every value in the current board
 * for that column (not a fixed 1-32 league rank, unlike SoS) — higher
 * Net FP / DSR is offense-friendly, so it reads greener; lower reads redder. */
function percentileColor(value: number | null, pool: Array<number | null>): string {
  if (value == null) return 'transparent'
  const values = pool.filter((entry): entry is number => entry != null)
  if (values.length < 2) return 'transparent'
  const sorted = [...values].sort((a, b) => a - b)
  const atOrBelow = sorted.filter((entry) => entry <= value).length
  const t = (atOrBelow - 1) / (sorted.length - 1)
  const hue = 120 * t
  return `hsla(${hue}, 70%, 35%, 0.55)`
}

function formatValue(value: number | null, decimals: number): string {
  if (value == null) return '—'
  return value.toFixed(decimals)
}

export function WeekWorkbookView({ onNavigateTab }: WeekWorkbookViewProps = {}) {
  const [week, setWeek] = useState(() => {
    try {
      const linked = sessionStorage.getItem(CROSS_LINK_WEEK_KEY)
      if (linked) {
        sessionStorage.removeItem(CROSS_LINK_WEEK_KEY)
        const parsed = Number(linked)
        if (parsed >= 1 && parsed <= 18) return parsed
      }
    } catch {
      // private mode
    }
    return 10
  })
  const [leagues, setLeagues] = useState<EspnLeague[]>([])
  const [leagueId, setLeagueId] = useState(() => {
    try {
      return localStorage.getItem(WORKBOOK_LEAGUE_STORAGE_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [includeFa, setIncludeFa] = useState(true)
  const [sosCrossPosition, setSosCrossPosition] = useState<SosPosition>('RB')
  const [window, setWindow] = useState<WorkbookWindow>('l4')
  const [customStart, setCustomStart] = useState(1)
  const [customEnd, setCustomEnd] = useState(17)
  const [scoring, setScoring] = useState<WorkbookScoring>('ppr')
  const [slate, setSlate] = useState<WorkbookSlate>('main')
  const [subTab, setSubTab] = useState<WorkbookSubTab>('matchups')
  const [data, setData] = useState<WorkbookMatchupsResponse | null>(null)
  const [error, setError] = useState('')
  const [needsToken, setNeedsToken] = useState(false)
  const [authRetry, setAuthRetry] = useState(0)
  const [loading, setLoading] = useState(true)

  const [explainTarget, setExplainTarget] = useState<{ team: string; metric: WorkbookExplainMetric; label: string } | null>(null)
  const [explainData, setExplainData] = useState<WorkbookExplainResponse | null>(null)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState('')

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
        // board works without league list
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
      // ignore quota / private mode
    }
  }, [leagueId])

  useEffect(() => {
    if (subTab !== 'matchups') return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      setNeedsToken(false)
      try {
        const payload = await draftApi.workbookMatchups({
          week,
          window,
          scoring,
          slate,
          startWeek: window === 'custom' ? customStart : undefined,
          endWeek: window === 'custom' ? customEnd : undefined,
          leagueId: leagueId || undefined,
          includeFa
        })
        if (cancelled) return
        setData(payload)
      } catch (err) {
        if (cancelled) return
        setData(null)
        setNeedsToken(isApiAuthError(err))
        setError(err instanceof Error ? err.message : 'Could not load the Workbook board.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [subTab, week, window, scoring, slate, customStart, customEnd, leagueId, includeFa, authRetry])

  const p2Controls = useMemo(
    () => ({ week, window, customStart, customEnd, scoring }),
    [week, window, customStart, customEnd, scoring]
  )

  const subTabTitle =
    subTab === 'matchups'
      ? 'Workbook Net Matchups'
      : subTab === 'top'
        ? 'Time of Possession'
        : subTab === 'pace'
          ? 'Offensive Pace'
          : subTab === 'injuries'
            ? 'League Injuries'
            : subTab === 'matrices'
              ? 'Positional Matrices'
              : subTab === 'feeders'
                ? 'Feeder Tables'
                : subTab === 'pool'
                  ? 'DFS Salary Pool'
                  : subTab === 'shadow'
                    ? 'Clay WR Shadows'
                    : 'OL/DL Proxy'

  const allRows = useMemo(() => data?.games.flatMap((game) => game.rows) ?? [], [data])
  const pools = useMemo(() => {
    const result: Record<string, Array<number | null>> = {}
    for (const column of COLUMNS) {
      result[column.key] = allRows.map((row) => column.getValue(row))
    }
    return result
  }, [allRows])

  const highlightsByTeam = useMemo(() => {
    const map = new Map<string, WorkbookHighlight[]>()
    for (const entry of data?.highlights ?? []) {
      const list = map.get(entry.matchupTeam) ?? []
      list.push(entry)
      map.set(entry.matchupTeam, list)
    }
    return map
  }, [data?.highlights])

  const goToSos = () => {
    try {
      sessionStorage.setItem(CROSS_LINK_POSITION_KEY, sosCrossPosition)
    } catch {
      // private mode
    }
    onNavigateTab?.('week-sos')
  }

  const openExplain = (team: string, metric: WorkbookExplainMetric, label: string) => {
    setSosCrossPosition(sosPositionForMetric(metric))
    setExplainTarget({ team, metric, label })
    setExplainData(null)
    setExplainError('')
    setExplainLoading(true)
    draftApi
      .workbookExplain({
        team,
        week,
        metric,
        window,
        scoring,
        startWeek: window === 'custom' ? customStart : undefined,
        endWeek: window === 'custom' ? customEnd : undefined
      })
      .then((payload) => setExplainData(payload))
      .catch((err) => setExplainError(err instanceof Error ? err.message : 'Could not load explain detail.'))
      .finally(() => setExplainLoading(false))
  }

  const weekLabel =
    window === 'custom' ? `weeks ${Math.min(customStart, customEnd)}–${Math.max(customStart, customEnd)}` : window

  return (
    <div className="space-y-4" data-testid="week-workbook-view">
      <section className="mb-1 grid gap-3 rounded-2xl border border-line bg-gradient-to-r from-panel to-ink p-4 shadow-glow lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="eyebrow">Workbook</p>
          <h2 className="text-lg font-semibold">{subTabTitle}</h2>
          <p className="mt-1 text-xs text-muted">
            Household Net Matchups · green = offense-friendly cell · red = tough · inspired by Majesstik/OWS, computed by us
          </p>
          {data && (
            <p className="mt-1 text-[11px] text-muted" data-testid="workbook-source-line">
              {[
                `window ${weekLabel}`,
                data.ratedThroughWeek > 0 ? `rated through week ${data.ratedThroughWeek}` : 'no completed weeks yet',
                data.stale ? 'snapshot fallback' : data.source
              ].join(' · ')}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Week
            <select
              data-testid="workbook-week"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={week}
              onChange={(event) => setWeek(Number(event.target.value))}
            >
              {WEEK_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  W{option}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">Window</span>
            <div className="flex flex-wrap rounded-lg border border-line p-0.5" role="group" aria-label="Stat window">
              {(
                [
                  ['l4', 'L4'],
                  ['season', 'Season']
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  data-testid={`workbook-window-${key}`}
                  className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                    window === key ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                  }`}
                  onClick={() => setWindow(key)}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                data-testid="workbook-window-custom"
                className={`rounded-md px-2.5 py-1.5 text-xs font-semibold ${
                  window === 'custom' ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                }`}
                onClick={() => setWindow('custom')}
              >
                Custom
              </button>
            </div>
          </div>
          {window === 'custom' && (
            <>
              <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
                From
                <select
                  data-testid="workbook-start-week"
                  className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
                  value={customStart}
                  onChange={(event) => setCustomStart(Number(event.target.value))}
                >
                  {WEEK_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      W{option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
                To
                <select
                  data-testid="workbook-end-week"
                  className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
                  value={customEnd}
                  onChange={(event) => setCustomEnd(Number(event.target.value))}
                >
                  {WEEK_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      W{option}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Scoring
            <select
              data-testid="workbook-scoring"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={scoring}
              onChange={(event) => setScoring(event.target.value as WorkbookScoring)}
            >
              <option value="ppr">Full PPR</option>
              <option value="half_ppr">Half PPR</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Slate
            <select
              data-testid="workbook-slate"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={slate}
              onChange={(event) => setSlate(event.target.value as WorkbookSlate)}
            >
              <option value="main">Main slate</option>
              <option value="all">All games</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            League
            <select
              data-testid="workbook-league-select"
              className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
              value={leagueId}
              onChange={(event) => setLeagueId(event.target.value)}
            >
              <option value="">No ESPN overlay</option>
              {(leagues ?? []).map((league) => (
                <option key={league.id} value={league.id}>
                  {league.name}
                </option>
              ))}
            </select>
          </label>
          {leagueId && (
            <label className="flex items-center gap-2 pb-2 text-xs text-muted">
              <input
                type="checkbox"
                data-testid="workbook-include-fa"
                className="rounded border-line"
                checked={includeFa}
                onChange={(event) => setIncludeFa(event.target.checked)}
              />
              Include FA
            </label>
          )}
        </div>
      </section>

      <WorkbookSubNav active={subTab} onChange={setSubTab} />

      {subTab === 'matchups' && needsToken && (
        <ApiTokenPrompt onSaved={() => setAuthRetry((n) => n + 1)} />
      )}

      {subTab === 'matchups' && error && !needsToken && (
        <div role="alert" className="rounded-lg border border-rose-400/30 bg-rose-400/10 px-4 py-2 text-xs text-rose-100">
          {error}
        </div>
      )}

      {subTab === 'matchups' && data?.stale && (
        <div
          data-testid="workbook-stale-banner"
          className="rounded-lg border border-amber-300/30 bg-amber-300/10 px-4 py-2 text-xs text-amber-100"
        >
          Showing a packaged snapshot — live nflverse data was unreachable. Numbers may be out of date.
        </div>
      )}

      {subTab === 'matchups' && data?.overlayError && leagueId && (
        <p className="rounded-lg border border-amber-300/20 bg-amber-300/5 px-4 py-2 text-xs text-amber-100">
          ESPN highlights unavailable — showing the Net board only.
        </p>
      )}

      {subTab === 'top' && <WorkbookTopPanel controls={p2Controls} />}
      {subTab === 'pace' && <WorkbookPacePanel controls={p2Controls} />}
      {subTab === 'injuries' && <WorkbookInjuriesPanel controls={p2Controls} leagueId={leagueId} />}
      {subTab === 'matrices' && <WorkbookMatricesPanel controls={p2Controls} />}
      {subTab === 'feeders' && <WorkbookFeedersPanel controls={p2Controls} />}
      {subTab === 'pool' && <WorkbookPoolView controls={p2Controls} />}
      {subTab === 'oldl' && <WorkbookOldlPanel controls={p2Controls} />}
      {subTab === 'shadow' && <WorkbookClayShadowPanel controls={p2Controls} />}

      {subTab === 'matchups' && (
      <section className="panel overflow-hidden">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Net Matchups</p>
            <h2>
              Week {week} · {slate === 'main' ? 'Main slate' : 'All games'}
            </h2>
          </div>
          {loading && <p className="text-xs text-muted">Loading…</p>}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-table">
            <thead>
              <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
                <th className="sticky left-0 z-10 bg-panel px-2 py-2">Team</th>
                <th className="px-2 py-2">Opp</th>
                {COLUMNS.map((column) => (
                  <th key={column.key} className="px-2 py-2 text-center font-semibold">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.games ?? []).map((game) => (
                <Fragment key={`${game.away}-${game.home}`}>
                  <tr className="border-b border-line/40 bg-ink/40">
                    <td colSpan={COLUMNS.length + 2} className="px-2 py-1 text-[10px] font-semibold text-muted">
                      {game.away} @ {game.home}
                      {!game.mainSlate && <span className="ml-2 text-amber-200">non-main slate</span>}
                    </td>
                  </tr>
                  {game.rows.map((row) => (
                    <tr key={row.team} className="border-b border-line/60" data-testid={`workbook-row-${row.team}`}>
                      <td className="sticky left-0 z-10 bg-panel px-2 py-1.5 font-bold">
                        {row.team}
                        <span className="ml-1 text-[9px] font-semibold text-muted">
                          {row.homeAway === 'home' ? 'HOME' : 'AWAY'}
                        </span>
                        {(highlightsByTeam.get(row.team)?.length ?? 0) > 0 && (
                          <span
                            data-testid={`workbook-highlight-badge-${row.team}`}
                            className="ml-1.5 inline-flex min-w-[1.1rem] items-center justify-center rounded-full bg-mint/20 px-1 text-[9px] font-black text-mint"
                            title={highlightTooltip(highlightsByTeam.get(row.team) ?? [])}
                          >
                            {highlightsByTeam.get(row.team)?.length}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-muted">{row.opponent}</td>
                      {COLUMNS.map((column) => {
                        const value = column.getValue(row)
                        const reason = column.getReason?.(row)
                        const clickable = Boolean(column.explainMetric)
                        return (
                          <td
                            key={column.key}
                            data-testid={`workbook-cell-${row.team}-${column.key}`}
                            className={`px-1 py-1 text-center tabular-nums font-semibold ${
                              clickable ? 'cursor-pointer hover:underline' : ''
                            }`}
                            style={{ backgroundColor: percentileColor(value, pools[column.key] ?? []) }}
                            title={reason ? `No data: ${reason}` : undefined}
                            onClick={
                              column.explainMetric
                                ? () => openExplain(row.team, column.explainMetric!, column.label)
                                : undefined
                            }
                          >
                            {formatValue(value, column.decimals)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
              {!loading && !error && (data?.games.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length + 2} className="px-4 py-6 text-center text-muted">
                    No games scheduled for this week / slate.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      )}

      {subTab === 'matchups' && explainTarget && (
        <section
          className="panel p-4"
          data-testid="workbook-explain-panel"
          role="dialog"
          aria-label={`${explainTarget.team} ${explainTarget.label} explain`}
        >
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold">
              {explainTarget.team} · {explainTarget.label}
            </h3>
            <button
              type="button"
              className="button-secondary !px-2 !py-1 text-xs"
              onClick={() => setExplainTarget(null)}
            >
              Close
            </button>
          </div>
          {explainLoading && <p className="text-xs text-muted">Loading…</p>}
          {explainError && (
            <p role="alert" className="text-xs text-rose-200">
              {explainError}
            </p>
          )}
          {explainData && (
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted">OFF</p>
                <p className="text-lg font-bold text-mint">{formatValue(explainData.off, 1)}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted">DEF allowed</p>
                <p className="text-lg font-bold text-mint">{formatValue(explainData.def, 1)}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted">Net</p>
                <p className="text-lg font-bold text-mint">{formatValue(explainData.net, 1)}</p>
              </div>
              <p className="col-span-3 mt-1 text-[10px] text-muted">
                vs {explainData.opponent ?? 'bye'} · {explainData.window} · {explainData.scoring.replace('_', ' ')}
              </p>
            </div>
          )}
        </section>
      )}

      {subTab === 'matchups' && data && (
        <p data-testid="workbook-attribution" className="px-1 text-[10px] text-muted">
          {data.attribution}
        </p>
      )}

      {subTab === 'matchups' && (
      <div className="flex flex-wrap items-center gap-3 px-1">
        <button
          type="button"
          data-testid="workbook-sos-cross-link"
          className="text-xs font-semibold text-mint hover:underline"
          onClick={goToSos}
        >
          See season SoS for {sosCrossPosition}
        </button>
        {leagueId && (data?.joinStats?.matched ?? 0) > 0 && (
          <span className="text-[10px] text-muted">
            {data?.joinStats?.matched} ESPN player{data?.joinStats?.matched === 1 ? '' : 's'} matched this week
          </span>
        )}
      </div>
      )}
    </div>
  )
}
