import { Fragment, useEffect, useState } from 'react'
import { draftApi } from '../api/client'
import type { WorkbookP2Controls } from './WeekWorkbookP2Tabs'
import type { WorkbookOldlResponse } from './types'

function windowQuery(controls: WorkbookP2Controls) {
  return {
    week: controls.week,
    window: controls.window,
    startWeek: controls.window === 'custom' ? controls.customStart : undefined,
    endWeek: controls.window === 'custom' ? controls.customEnd : undefined
  }
}

function formatRate(value: number | null): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function formatEpa(value: number | null): string {
  if (value == null) return '—'
  return value.toFixed(3)
}

function roleLabel(role: string): string {
  if (role === 'offense_ol') return 'OL proxy'
  if (role === 'defense_dl') return 'DL proxy'
  return role
}

export function WorkbookOldlPanel({ controls }: { controls: WorkbookP2Controls }) {
  const [data, setData] = useState<WorkbookOldlResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const payload = await draftApi.workbookOldl(windowQuery(controls))
        if (cancelled) return
        setData(payload)
      } catch (err) {
        if (cancelled) return
        setData(null)
        setError(err instanceof Error ? err.message : 'Could not load OL/DL proxy data.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [controls.week, controls.window, controls.customStart, controls.customEnd])

  return (
    <section className="panel overflow-hidden" data-testid="workbook-oldl-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">OL / DL</p>
          <h2>Pass-pressure proxy board</h2>
          <p
            className="mt-1 text-[11px] text-amber-100"
            data-testid="workbook-oldl-disclaimer"
            title="Proxy metrics from nflverse dropbacks — not Football Outsiders."
          >
            Proxy — nflverse pressure / sack / EPA allowed; not Football Outsiders.
          </p>
        </div>
        {loading && <p className="text-xs text-muted">Loading…</p>}
      </div>

      {error && (
        <p role="alert" className="px-4 py-2 text-xs text-rose-200">
          {error}
        </p>
      )}

      {data?.stale && (
        <p className="px-4 py-2 text-xs text-amber-100" data-testid="workbook-oldl-stale">
          Snapshot fallback — numbers may be stale.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-oldl-table">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <th className="px-3 py-2">Team</th>
              <th className="px-3 py-2">Side</th>
              <th className="px-3 py-2 text-right">Pressure allowed</th>
              <th className="px-3 py-2 text-right">Sack rate</th>
              <th className="px-3 py-2 text-right">EPA / dropback</th>
              <th className="px-3 py-2 text-right">Pressure rank</th>
            </tr>
          </thead>
          <tbody>
            {(data?.games ?? []).map((game) => (
              <Fragment key={`${game.away}-${game.home}`}>
                <tr className="border-b border-line/40 bg-ink/40">
                  <td colSpan={6} className="px-2 py-1 text-[10px] font-semibold text-muted">
                    {game.away} @ {game.home}
                  </td>
                </tr>
                {game.rows.map((row) => (
                  <tr
                    key={`${game.away}-${game.home}-${row.team}-${row.role}`}
                    className="border-b border-line/60"
                    data-testid={`workbook-oldl-row-${row.team}`}
                  >
                    <td className="px-3 py-1.5 font-bold">{row.team}</td>
                    <td className="px-3 py-1.5">
                      <span className="rounded bg-amber-400/20 px-1.5 py-0.5 text-[9px] font-bold uppercase text-amber-100">
                        {roleLabel(row.role)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{formatRate(row.pressureRateAllowed)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{formatRate(row.sackRateAllowed)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{formatEpa(row.epaPerDropbackAllowed)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted">
                      {row.rankPressure ?? '—'}
                    </td>
                  </tr>
                ))}
              </Fragment>
            ))}
            {!loading && !error && (data?.games.length ?? 0) === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted">
                  No games for this week.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {data?.disclaimer && (
        <p className="px-4 pb-3 text-[10px] text-muted" data-testid="workbook-oldl-footer">
          {data.disclaimer}
        </p>
      )}
    </section>
  )
}
