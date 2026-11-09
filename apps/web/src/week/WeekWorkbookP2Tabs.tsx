import { useEffect, useMemo, useState } from 'react'
import { draftApi } from '../api/client'
import type {
  WorkbookInjuriesResponse,
  WorkbookMatricesResponse,
  WorkbookMatrixGroup,
  WorkbookMatrixMetric,
  WorkbookMatrixTeamRow,
  WorkbookMatrixTierColor,
  WorkbookMatrixTertile,
  WorkbookPaceResponse,
  WorkbookScoring,
  WorkbookSubTab,
  WorkbookTopResponse,
  WorkbookWindow
} from './types'

export const WORKBOOK_SUB_TABS: Array<{ id: WorkbookSubTab; label: string; testId: string }> = [
  { id: 'matchups', label: 'Matchups', testId: 'workbook-subnav-matchups' },
  { id: 'top', label: 'TOP', testId: 'workbook-subnav-top' },
  { id: 'pace', label: 'Pace', testId: 'workbook-subnav-pace' },
  { id: 'injuries', label: 'Injuries', testId: 'workbook-subnav-injuries' },
  { id: 'matrices', label: 'Matrices', testId: 'workbook-subnav-matrices' }
]

export interface WorkbookP2Controls {
  week: number
  window: WorkbookWindow
  customStart: number
  customEnd: number
  scoring: WorkbookScoring
}

function windowQuery(controls: WorkbookP2Controls) {
  return {
    week: controls.week,
    window: controls.window,
    startWeek: controls.window === 'custom' ? controls.customStart : undefined,
    endWeek: controls.window === 'custom' ? controls.customEnd : undefined
  }
}

function formatValue(value: number | null, decimals: number): string {
  if (value == null) return '—'
  return value.toFixed(decimals)
}

function tierAbbrev(tier: WorkbookMatrixTertile | null): string {
  if (tier === 'top') return 'T'
  if (tier === 'mid') return 'M'
  if (tier === 'bottom') return 'B'
  return '—'
}

function tierCellStyle(color: WorkbookMatrixTierColor | null): string {
  switch (color) {
    case 'green':
      return 'hsla(120, 70%, 35%, 0.55)'
    case 'red':
      return 'hsla(0, 70%, 40%, 0.55)'
    case 'neutral':
      return 'hsla(48, 70%, 40%, 0.45)'
    default:
      return 'transparent'
  }
}

function injuryStatusClass(status: string): string {
  const upper = status.toUpperCase()
  if (upper === 'O' || upper === 'OUT') return 'bg-rose-500/25 text-rose-100'
  if (upper === 'D' || upper === 'DOUBTFUL') return 'bg-orange-500/25 text-orange-100'
  if (upper === 'Q' || upper === 'QUESTIONABLE') return 'bg-amber-400/25 text-amber-100'
  return 'bg-slate-500/20 text-slate-200'
}

export type WorkbookSubNavProps = {
  active: WorkbookSubTab
  onChange: (tab: WorkbookSubTab) => void
}

export function WorkbookSubNav({ active, onChange }: WorkbookSubNavProps) {
  return (
    <nav
      className="flex flex-wrap gap-1 rounded-lg border border-line bg-ink/40 p-0.5"
      data-testid="workbook-subnav"
      role="tablist"
      aria-label="Workbook views"
    >
      {WORKBOOK_SUB_TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          data-testid={tab.testId}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
            active === tab.id ? 'bg-mint text-ink' : 'text-muted hover:text-white'
          }`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

export function WorkbookTopPanel({ controls }: { controls: WorkbookP2Controls }) {
  const [data, setData] = useState<WorkbookTopResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const payload = await draftApi.workbookTop(windowQuery(controls))
        if (cancelled) return
        setData(payload)
      } catch (err) {
        if (cancelled) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load TOP data.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [controls.week, controls.window, controls.customStart, controls.customEnd])

  const sorted = useMemo(
    () => [...(data?.teams ?? [])].sort((a, b) => a.team.localeCompare(b.team)),
    [data?.teams]
  )

  return (
    <section className="panel overflow-hidden" data-testid="workbook-top-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Time of possession</p>
          <h2>TOP % by team</h2>
          {data?.method === 'plays_share_proxy' && (
            <p className="mt-1 text-[11px] text-amber-100">Plays-share proxy — not drive-clock TOP</p>
          )}
        </div>
        {loading && <p className="text-xs text-muted">Loading…</p>}
      </div>
      {error && (
        <p role="alert" className="px-4 py-2 text-xs text-rose-200">
          {error}
        </p>
      )}
      {data?.stale && (
        <p className="px-4 py-2 text-xs text-amber-100" data-testid="workbook-top-stale">
          Snapshot fallback — numbers may be stale.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-top-table">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <th className="px-3 py-2">Team</th>
              <th className="px-3 py-2 text-right">TOP %</th>
              <th className="px-3 py-2 text-right">Games</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.team} className="border-b border-line/60" data-testid={`workbook-top-row-${row.team}`}>
                <td className="px-3 py-1.5 font-bold">{row.team}</td>
                <td className="px-3 py-1.5 text-right tabular-nums font-semibold">
                  {formatValue(row.topPct, 1)}
                  {row.method === 'plays_share_proxy' && (
                    <span
                      className="ml-1.5 rounded bg-amber-400/20 px-1 text-[9px] font-bold uppercase text-amber-100"
                      title="Plays-share proxy"
                    >
                      proxy
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums text-muted">{row.sampleGames}</td>
              </tr>
            ))}
            {!loading && !error && sorted.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-muted">
                  No TOP data for this window.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {data?.attribution && (
        <p className="px-4 pb-3 text-[10px] text-muted" data-testid="workbook-top-attribution">
          {data.attribution}
        </p>
      )}
    </section>
  )
}

export function WorkbookPacePanel({ controls }: { controls: WorkbookP2Controls }) {
  const [data, setData] = useState<WorkbookPaceResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const payload = await draftApi.workbookPace(windowQuery(controls))
        if (cancelled) return
        setData(payload)
      } catch (err) {
        if (cancelled) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load pace data.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [controls.week, controls.window, controls.customStart, controls.customEnd])

  const sorted = useMemo(
    () => [...(data?.teams ?? [])].sort((a, b) => a.team.localeCompare(b.team)),
    [data?.teams]
  )

  return (
    <section className="panel overflow-hidden" data-testid="workbook-pace-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Pace</p>
          <h2>Offensive plays per game</h2>
        </div>
        {loading && <p className="text-xs text-muted">Loading…</p>}
      </div>
      {error && (
        <p role="alert" className="px-4 py-2 text-xs text-rose-200">
          {error}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-pace-table">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <th className="px-3 py-2">Team</th>
              <th className="px-3 py-2 text-right">Plays/G</th>
              <th className="px-3 py-2 text-right">Pass %</th>
              <th className="px-3 py-2 text-right">Run %</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.team} className="border-b border-line/60" data-testid={`workbook-pace-row-${row.team}`}>
                <td className="px-3 py-1.5 font-bold">{row.team}</td>
                <td className="px-3 py-1.5 text-right tabular-nums font-semibold">
                  {formatValue(row.playsPerGame, 1)}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums text-muted">
                  {row.passRate != null ? `${(row.passRate * 100).toFixed(1)}%` : '—'}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums text-muted">
                  {row.runRate != null ? `${(row.runRate * 100).toFixed(1)}%` : '—'}
                </td>
              </tr>
            ))}
            {!loading && !error && sorted.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted">
                  No pace data for this window.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {data?.attribution && (
        <p className="px-4 pb-3 text-[10px] text-muted" data-testid="workbook-pace-attribution">
          {data.attribution}
        </p>
      )}
    </section>
  )
}

export function WorkbookInjuriesPanel({
  controls,
  leagueId
}: {
  controls: Pick<WorkbookP2Controls, 'week'>
  leagueId: string
}) {
  const [data, setData] = useState<WorkbookInjuriesResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [teamFilter, setTeamFilter] = useState('')

  useEffect(() => {
    if (!leagueId) {
      setData(null)
      setError('')
      setLoading(false)
      return
    }
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const payload = await draftApi.workbookInjuries({ week: controls.week, leagueId })
        if (cancelled) return
        setData(payload)
      } catch (err) {
        if (cancelled) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load injuries.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [controls.week, leagueId])

  const teams = useMemo(() => {
    const set = new Set((data?.injuries ?? []).map((row) => row.team).filter(Boolean))
    return [...set].sort()
  }, [data?.injuries])

  const filtered = useMemo(() => {
    const list = data?.injuries ?? []
    if (!teamFilter) return list
    return list.filter((row) => row.team === teamFilter)
  }, [data?.injuries, teamFilter])

  if (!leagueId) {
    return (
      <section className="panel p-4" data-testid="workbook-injuries-panel">
        <p className="text-sm text-muted">Select an ESPN league above to load injury statuses.</p>
      </section>
    )
  }

  return (
    <section className="panel overflow-hidden" data-testid="workbook-injuries-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Injuries</p>
          <h2>Week {controls.week} · ESPN statuses</h2>
        </div>
        <div className="flex items-end gap-2">
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Team
            <select
              data-testid="workbook-injuries-team-filter"
              className="rounded-lg border border-line bg-ink px-2 py-1.5 text-xs font-semibold normal-case tracking-normal text-slate-100"
              value={teamFilter}
              onChange={(event) => setTeamFilter(event.target.value)}
            >
              <option value="">All teams</option>
              {teams.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </label>
          {loading && <p className="text-xs text-muted">Loading…</p>}
        </div>
      </div>
      {data?.warnings?.includes('injuries_unavailable') && (
        <p className="px-4 py-2 text-xs text-amber-100" data-testid="workbook-injuries-unavailable">
          ESPN injuries unavailable — try again later.
        </p>
      )}
      {error && (
        <p role="alert" className="px-4 py-2 text-xs text-rose-200">
          {error}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-injuries-table">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <th className="px-3 py-2">Player</th>
              <th className="px-3 py-2">Team</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Body</th>
              <th className="px-3 py-2">Practice</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.playerId} className="border-b border-line/60" data-testid={`workbook-injury-${row.playerId}`}>
                <td className="px-3 py-1.5 font-semibold">{row.name}</td>
                <td className="px-3 py-1.5 text-muted">{row.team}</td>
                <td className="px-3 py-1.5">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${injuryStatusClass(row.status)}`}
                  >
                    {row.status || '—'}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-muted">{row.bodyPart ?? '—'}</td>
                <td className="px-3 py-1.5 text-muted">{row.practice ?? '—'}</td>
              </tr>
            ))}
            {!loading && !error && filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted">
                  No injured players reported for this league.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

const MATRIX_GROUPS: Array<{ id: WorkbookMatrixGroup; label: string }> = [
  { id: 'qb', label: 'QB' },
  { id: 'wr', label: 'WR' },
  { id: 'te', label: 'TE' },
  { id: 'rb', label: 'RB' },
  { id: 'dsr', label: 'DSR' }
]

const MATRIX_METRICS: Array<{ id: WorkbookMatrixMetric; label: string }> = [
  { id: 'fp_per_game', label: 'FP/G' },
  { id: 'targets_per_game', label: 'Tgt/G' },
  { id: 'yards_per_game', label: 'Yds/G' },
  { id: 'tds_per_game', label: 'TD/G' },
  { id: 'dsr', label: 'DSR' }
]

function metricOptionsForGroup(group: WorkbookMatrixGroup): WorkbookMatrixMetric[] {
  if (group === 'dsr') return ['dsr']
  return ['fp_per_game', 'targets_per_game', 'yards_per_game', 'tds_per_game']
}

function MatrixCell({ cell, decimals }: { cell: WorkbookMatrixTeamRow['off']; decimals: number }) {
  return (
    <td
      className="px-1 py-1 text-center tabular-nums font-semibold"
      style={{ backgroundColor: tierCellStyle(cell.tierColor) }}
      title={cell.tier ? `Tertile: ${cell.tier}` : undefined}
    >
      <span className="mr-1 text-[9px] font-black text-muted">{tierAbbrev(cell.tier)}</span>
      {formatValue(cell.value, decimals)}
    </td>
  )
}

export function WorkbookMatricesPanel({ controls }: { controls: WorkbookP2Controls }) {
  const [group, setGroup] = useState<WorkbookMatrixGroup>('wr')
  const [metric, setMetric] = useState<WorkbookMatrixMetric>('fp_per_game')
  const [data, setData] = useState<WorkbookMatricesResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const allowed = metricOptionsForGroup(group)
    if (!allowed.includes(metric)) {
      setMetric(allowed[0])
    }
  }, [group, metric])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const payload = await draftApi.workbookMatrices(group, {
          ...windowQuery(controls),
          metric,
          scoring: controls.scoring
        })
        if (cancelled) return
        setData(payload)
      } catch (err) {
        if (cancelled) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load matrices.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [group, metric, controls.week, controls.window, controls.customStart, controls.customEnd, controls.scoring])

  const decimals = metric === 'dsr' ? 3 : 1
  const sorted = useMemo(
    () => [...(data?.teams ?? [])].sort((a, b) => a.team.localeCompare(b.team)),
    [data?.teams]
  )

  return (
    <section className="panel overflow-hidden" data-testid="workbook-matrices-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Positional matrices</p>
          <h2>OFF / DEF / Net · league tertiles</h2>
          <p className="mt-1 text-[11px] text-muted">T / M / B = top · mid · bottom third for this window</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Group
            <select
              data-testid="workbook-matrices-group"
              className="rounded-lg border border-line bg-ink px-2 py-1.5 text-xs font-semibold normal-case tracking-normal text-slate-100"
              value={group}
              onChange={(event) => setGroup(event.target.value as WorkbookMatrixGroup)}
            >
              {MATRIX_GROUPS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
            Metric
            <select
              data-testid="workbook-matrices-metric"
              className="rounded-lg border border-line bg-ink px-2 py-1.5 text-xs font-semibold normal-case tracking-normal text-slate-100"
              value={metric}
              onChange={(event) => setMetric(event.target.value as WorkbookMatrixMetric)}
            >
              {MATRIX_METRICS.filter((option) => metricOptionsForGroup(group).includes(option.id)).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {loading && <p className="text-xs text-muted">Loading…</p>}
        </div>
      </div>
      {error && (
        <p role="alert" className="px-4 py-2 text-xs text-rose-200">
          {error}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-matrices-table">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <th className="px-3 py-2">Team</th>
              <th className="px-3 py-2 text-center">OFF</th>
              <th className="px-3 py-2 text-center">DEF</th>
              <th className="px-3 py-2 text-center">Net</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.team} className="border-b border-line/60" data-testid={`workbook-matrix-row-${row.team}`}>
                <td className="px-3 py-1.5 font-bold">{row.team}</td>
                <MatrixCell cell={row.off} decimals={decimals} />
                <MatrixCell cell={row.def} decimals={decimals} />
                <MatrixCell cell={row.net} decimals={decimals} />
              </tr>
            ))}
            {!loading && !error && sorted.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted">
                  No matrix data for this selection.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {data?.attribution && (
        <p className="px-4 pb-3 text-[10px] text-muted" data-testid="workbook-matrices-attribution">
          {data.attribution}
        </p>
      )}
    </section>
  )
}
