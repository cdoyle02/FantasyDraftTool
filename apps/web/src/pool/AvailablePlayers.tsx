import { useMemo, useState } from 'react'
import { PositionPill } from '../components/PositionPill'
import { keptPlayerIds, teamForPick, useDraftStore } from '../store/draftStore'
import type { Player, UserAdjustment } from '../types'
import { AdpSourceHeader } from './AdpSourceHeader'
import { adpForSource, compareAvailablePlayers, formatAdp, type AdpSource, type SortDir } from './adp'

function KeeperDialog({ player, close }: { player: Player; close: () => void }) {
  const settings = useDraftStore((state) => state.settings)
  const assignKeeper = useDraftStore((state) => state.assignKeeper)
  const [teamId, setTeamId] = useState(Math.min(settings.userTeam, settings.teamCount))

  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4">
    <section className="w-full max-w-md rounded-2xl border border-line bg-panel p-6" role="dialog" aria-modal="true" aria-labelledby="keeper-title">
      <p className="eyebrow">Pre-draft keeper</p>
      <h2 id="keeper-title" className="text-2xl font-semibold">{player.name}</h2>
      <p className="mt-1 text-sm text-muted">Place on a team as a 1st-round keeper. The player leaves the pool but the draft clock stays at pick 1.</p>
      <p className="mt-4 text-xs font-semibold text-muted">Choose team</p>
      <div className="mt-2 flex flex-wrap gap-1">
        {Array.from({ length: settings.teamCount }, (_, index) => index + 1).map((team) => {
          const isUser = team === settings.userTeam
          return <button
            key={team}
            type="button"
            aria-pressed={teamId === team}
            onClick={() => setTeamId(team)}
            className={`rounded-md px-2.5 py-1 text-[11px] font-bold ${teamId === team ? 'bg-mint text-ink' : isUser ? 'border border-mint/40 text-mint hover:bg-mint/5' : 'text-muted hover:bg-white/5'}`}
          >
            {isUser ? 'YOU' : `T${team}`}
          </button>
        })}
      </div>
      <div className="mt-6 flex justify-end gap-3">
        <button className="button-secondary" onClick={close}>Cancel</button>
        <button className="button-primary" onClick={async () => { await assignKeeper(player, teamId); close() }}>Place keeper</button>
      </div>
    </section>
  </div>
}

function AdjustmentDialog({ player, close }: { player: Player; close: () => void }) {
  const existing = useDraftStore((state) => state.adjustments[player.id])
  const adjustPlayer = useDraftStore((state) => state.adjustPlayer)
  const [pointsDelta, setPointsDelta] = useState(existing?.pointsDelta ?? 0)
  const [tierOverride, setTierOverride] = useState<number | undefined>(existing?.tierOverride)
  const [tag, setTag] = useState<UserAdjustment['tag'] | ''>(existing?.tag ?? '')
  const [note, setNote] = useState(existing?.note ?? '')

  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4">
    <section className="w-full max-w-lg rounded-2xl border border-line bg-panel p-6" role="dialog" aria-modal="true" aria-labelledby="adjustment-title">
      <p className="eyebrow">Your opinion layer</p>
      <h2 id="adjustment-title" className="text-2xl font-semibold">{player.name}</h2>
      <p className="mt-1 text-sm text-muted">These settings survive projection re-imports.</p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <label className="field">Points boost / fade<input type="number" step="1" value={pointsDelta} onChange={(event) => setPointsDelta(Number(event.target.value))} /></label>
        <label className="field">Tier override<input type="number" min="1" placeholder={`Imported: ${player.tier}`} value={tierOverride ?? ''} onChange={(event) => setTierOverride(event.target.value ? Number(event.target.value) : undefined)} /></label>
        <label className="field sm:col-span-2">Tag<select value={tag} onChange={(event) => setTag(event.target.value as typeof tag)}><option value="">None</option><option value="myGuy">My guy</option><option value="avoid">Never draft</option></select></label>
        <label className="field sm:col-span-2">Note<textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Why you are higher or lower than consensus" /></label>
      </div>
      <div className="mt-6 flex justify-end gap-3"><button className="button-secondary" onClick={close}>Cancel</button><button className="button-primary" onClick={async () => { await adjustPlayer(player.id, { pointsDelta, tierOverride, tag: tag || undefined, note }); close() }}>Save adjustment</button></div>
    </section>
  </div>
}

export function AvailablePlayers() {
  const { players, adjustments, picks, keepers, adjustPlayer, settings, draftPlayer } = useDraftStore()
  const [filter, setFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<Player | null>(null)
  const [keeping, setKeeping] = useState<Player | null>(null)
  const [adpSource, setAdpSource] = useState<AdpSource>('adp')
  const [adpDir, setAdpDir] = useState<SortDir>('asc')
  const onClockTeam = teamForPick(picks.length + 1, settings.teamCount)
  const draftLabel = onClockTeam === settings.userTeam ? 'YOU' : `T${onClockTeam}`
  const rosterSize = useMemo(() => Object.values(settings.rosterSlots).reduce((sum, count) => sum + count, 0), [settings.rosterSlots])
  const keepersOnUserTeam = useMemo(
    () => keepers.filter((keeper) => keeper.teamId === settings.userTeam).length,
    [keepers, settings.userTeam]
  )
  const configuredKeeperSlots = settings.keeperSlots ?? keepersOnUserTeam
  const liveRounds = rosterSize - configuredKeeperSlots
  const draftFull = picks.length >= settings.teamCount * liveRounds
  const unavailable = useMemo(() => {
    const ids = keptPlayerIds(keepers)
    for (const pick of picks) ids.add(pick.playerId)
    return ids
  }, [picks, keepers])
  const available = useMemo(() => {
    return players
      .filter((player) => !unavailable.has(player.id) && (filter === 'ALL' || player.position === filter) && player.name.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => compareAvailablePlayers(a, b, adpSource, adpDir, adjustments))
  }, [players, unavailable, filter, search, adpSource, adpDir, adjustments])

  return <section className="panel min-h-0 lg:col-span-5">
    <div className="panel-heading"><div><p className="eyebrow">Player pool</p><h2>Available players <span className="font-normal text-muted">{available.length}</span></h2></div><input aria-label="Filter players by name" className="w-36 rounded-lg border border-line bg-ink px-3 py-2 text-xs outline-none focus:border-mint" placeholder="Filter names" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
    <div className="flex gap-1 overflow-x-auto border-b border-line px-4 py-2">{['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DST'].map((item) => <button key={item} onClick={() => setFilter(item)} className={`rounded-md px-2.5 py-1 text-[11px] font-bold ${filter === item ? 'bg-mint text-ink' : 'text-muted hover:bg-white/5'}`}>{item}</button>)}</div>
    <div className="max-h-[430px] overflow-auto"><table className="w-full text-left text-sm"><thead className="sticky top-0 bg-panel text-[10px] uppercase tracking-wider text-muted"><tr><th className="w-24 px-2 py-2">Actions</th><th className="px-4 py-2">Player</th><th>Proj</th><AdpSourceHeader source={adpSource} dir={adpDir} onSourceChange={(next) => { setAdpSource(next); setAdpDir('asc') }} onToggleDir={() => setAdpDir((current) => current === 'asc' ? 'desc' : 'asc')} /><th className="pr-4 text-right">Adjust</th></tr></thead><tbody>
      {available.map((player) => {
        const opinion = adjustments[player.id]
        const displayedTier = opinion?.tierOverride ?? player.tier
        const draftAriaLabel = onClockTeam === settings.userTeam
          ? `Draft ${player.name} to your team`
          : `Draft ${player.name} to Team ${onClockTeam}`
        return <tr key={player.id} className="border-t border-line/60 hover:bg-white/[.025]"><td className="px-2 py-2.5"><div className="flex gap-1"><button aria-label={draftAriaLabel} title={draftAriaLabel} disabled={draftFull} className="mini-button !border-mint/40 font-bold !text-mint disabled:pointer-events-none disabled:opacity-40" onClick={() => void draftPlayer(player)}>{draftLabel}</button><button aria-label={`Keep ${player.name}`} title="Place as keeper on a team" className="mini-button !border-amber-300/40 font-bold !text-amber-200" onClick={() => setKeeping(player)}>Keep</button></div></td><td className="px-4 py-2.5"><div className="flex items-center gap-2"><PositionPill position={player.position} /><div><div className="font-medium">{player.name} {opinion?.tag === 'myGuy' && <span title="My guy">★</span>}{opinion?.tag === 'avoid' && <span title="Avoid">⊘</span>}</div><div className="text-[10px] text-muted">{player.team} · Tier {displayedTier}{opinion?.pointsDelta ? ` · ${opinion.pointsDelta > 0 ? '+' : ''}${opinion.pointsDelta}` : ''}</div></div></div></td><td className="text-xs">{player.projectedPoints}</td><td className="text-xs tabular-nums">{formatAdp(adpForSource(player, adpSource))}</td><td className="pr-4"><div className="flex justify-end gap-1"><button aria-label={`Fade ${player.name}`} title="Fade player" className="mini-button" onClick={() => void adjustPlayer(player.id, { pointsDelta: (opinion?.pointsDelta ?? 0) - 5 })}>−</button><button aria-label={`Boost ${player.name}`} title="Boost player" className="mini-button" onClick={() => void adjustPlayer(player.id, { pointsDelta: (opinion?.pointsDelta ?? 0) + 5 })}>+</button><button aria-label={`Tag ${player.name} as my guy`} title="My guy" className={`mini-button ${opinion?.tag === 'myGuy' ? '!border-mint !text-mint' : ''}`} onClick={() => void adjustPlayer(player.id, { tag: opinion?.tag === 'myGuy' ? undefined : 'myGuy' })}>★</button><button aria-label={`Avoid ${player.name}`} title="Never draft" className={`mini-button ${opinion?.tag === 'avoid' ? '!border-rose-400 !text-rose-300' : ''}`} onClick={() => void adjustPlayer(player.id, { tag: opinion?.tag === 'avoid' ? undefined : 'avoid' })}>⊘</button><button aria-label={`Edit ${player.name} adjustment`} title="Edit adjustment" className="mini-button" onClick={() => setEditing(player)}>•••</button></div></td></tr>
      })}
    </tbody></table></div>
    {editing && <AdjustmentDialog player={editing} close={() => setEditing(null)} />}
    {keeping && <KeeperDialog player={keeping} close={() => setKeeping(null)} />}
  </section>
}
