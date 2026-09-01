import { useEffect, useMemo, useRef, useState } from 'react'
import { PositionPill } from './components/PositionPill'
import { parsePlayerCsv } from './data/csv'
import { AvailablePlayers } from './pool/AvailablePlayers'
import { rosterEntriesForTeam, keptPlayerIds, roundForPick, teamForPick, useDraftStore } from './store/draftStore'
import { assignRosterSlots, SLOT_LABELS } from './store/rosterSlots'
import type { DraftPick, LeagueSettings, Player, Recommendation } from './types'

function SetupDialog({ close }: { close: () => void }) {
  const settings = useDraftStore((state) => state.settings)
  const updateSettings = useDraftStore((state) => state.updateSettings)
  const [draft, setDraft] = useState(settings)

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" role="presentation">
      <section className="w-full max-w-2xl rounded-2xl border border-line bg-panel p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="setup-title">
        <div className="mb-6 flex items-start justify-between">
          <div><p className="eyebrow">League configuration</p><h2 id="setup-title" className="text-2xl font-semibold">Tune your draft room</h2></div>
          <button className="icon-button" onClick={close} aria-label="Close setup">×</button>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="field">League name<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
          <label className="field">Your draft slot<input type="number" min="1" max={draft.teamCount} value={draft.userTeam} onChange={(event) => setDraft({ ...draft, userTeam: Number(event.target.value) })} /></label>
          <label className="field">Teams<input type="number" min="4" max="20" value={draft.teamCount} onChange={(event) => setDraft({ ...draft, teamCount: Number(event.target.value) })} /></label>
          <label className="field">Scoring<select value={draft.scoring} onChange={(event) => setDraft({ ...draft, scoring: event.target.value as typeof draft.scoring })}><option value="PPR">Full PPR</option><option value="HALF_PPR">Half PPR</option><option value="STANDARD">Standard</option></select></label>
        </div>
        <fieldset className="mt-6"><legend className="mb-3 text-sm font-semibold text-white">Roster slots</legend><div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
          {Object.entries(draft.rosterSlots).map(([slot, count]) => <label key={slot} className="field text-center text-xs">{slot}<input className="text-center" type="number" min="0" max="12" value={count} onChange={(event) => setDraft({ ...draft, rosterSlots: { ...draft.rosterSlots, [slot]: Number(event.target.value) } })} /></label>)}
        </div></fieldset>
        <div className="mt-7 flex justify-end gap-3"><button className="button-secondary" onClick={close}>Cancel</button><button className="button-primary" onClick={async () => { await updateSettings(draft); close() }}>Save league</button></div>
      </section>
    </div>
  )
}

function ImportDialog({ close }: { close: () => void }) {
  const importPlayers = useDraftStore((state) => state.importPlayers)
  const [status, setStatus] = useState('Drop a FantasyPros-style CSV or choose a file.')
  const input = useRef<HTMLInputElement>(null)
  const load = async (file?: File) => {
    if (!file) return
    try {
      setStatus('Parsing player projections…')
      const players = await parsePlayerCsv(file)
      await importPlayers(players)
      setStatus(`Imported ${players.length} players. Adjustments remain a separate local layer.`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Import failed')
    }
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4">
      <section className="w-full max-w-xl rounded-2xl border border-line bg-panel p-6" role="dialog" aria-modal="true" aria-labelledby="import-title">
        <p className="eyebrow">Projection data</p><h2 id="import-title" className="text-2xl font-semibold">Import player CSV</h2>
        <button className="mt-6 w-full rounded-xl border border-dashed border-mint/50 bg-mint/5 p-10 text-center hover:bg-mint/10" onClick={() => input.current?.click()} onDrop={(event) => { event.preventDefault(); void load(event.dataTransfer.files[0]) }} onDragOver={(event) => event.preventDefault()}>
          <span className="block text-lg font-semibold text-mint">Choose CSV file</span><span className="mt-2 block text-sm text-muted">Player, Position, Team, Projected Points, ADP, Tier</span>
        </button>
        <input ref={input} hidden type="file" accept=".csv,text/csv" onChange={(event) => void load(event.target.files?.[0])} />
        <p className="mt-4 min-h-6 text-sm text-muted" aria-live="polite">{status}</p>
        <div className="mt-5 flex justify-end"><button className="button-primary" onClick={close}>Done</button></div>
      </section>
    </div>
  )
}

function PickSearch({ correctionId, onCorrectionDone }: { correctionId?: string; onCorrectionDone: () => void }) {
  const players = useDraftStore((state) => state.players)
  const picks = useDraftStore((state) => state.picks)
  const keepers = useDraftStore((state) => state.keepers)
  const draftPlayer = useDraftStore((state) => state.draftPlayer)
  const correctPick = useDraftStore((state) => state.correctPick)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const unavailable = useMemo(() => {
    const ids = keptPlayerIds(keepers)
    for (const pick of picks) ids.add(pick.playerId)
    return ids
  }, [picks, keepers])
  const results = useMemo(() => players.filter((player) => !unavailable.has(player.id) && `${player.name} ${player.team} ${player.position}`.toLowerCase().includes(query.toLowerCase())).slice(0, 7), [players, unavailable, query])
  const select = (player: Player) => {
    void (correctionId ? correctPick(correctionId, player) : draftPlayer(player))
    setQuery('')
    setActive(0)
    onCorrectionDone()
  }
  return <div className="relative">
    <label htmlFor="pick-search" className="sr-only">Search available players</label>
    <div className="flex items-center rounded-xl border border-line bg-ink/70 px-3 focus-within:border-mint">
      <span className="text-muted">⌕</span><input id="pick-search" className="w-full bg-transparent px-3 py-3 text-sm outline-none" placeholder={correctionId ? 'Choose the replacement player…' : 'Record a pick — search name, team, position…'} value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => {
        if (event.key === 'ArrowDown') { event.preventDefault(); setActive(Math.min(active + 1, results.length - 1)) }
        if (event.key === 'ArrowUp') { event.preventDefault(); setActive(Math.max(active - 1, 0)) }
        if (event.key === 'Enter' && results[active]) select(results[active])
        if (event.key === 'Escape') setQuery('')
      }} aria-expanded={Boolean(query)} aria-controls="pick-results" aria-autocomplete="list" />
      <kbd className="hidden rounded border border-line px-1.5 py-0.5 text-[10px] text-muted sm:block">↵ PICK</kbd>
    </div>
    {query && <ul id="pick-results" role="listbox" className="absolute z-30 mt-2 max-h-80 w-full overflow-auto rounded-xl border border-line bg-panel p-1 shadow-2xl">
      {results.map((player, index) => <li key={player.id}><button role="option" aria-selected={active === index} onMouseEnter={() => setActive(index)} onClick={() => select(player)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left ${active === index ? 'bg-mint/10' : ''}`}>
        <PositionPill position={player.position} /><span className="flex-1 font-medium">{player.name}</span><span className="text-xs text-muted">{player.team} · ADP {player.adp}</span>
      </button></li>)}
      {!results.length && <li className="p-4 text-center text-sm text-muted">No available players match.</li>}
    </ul>}
  </div>
}

function ScoreBar({ label, value, max = 100, title }: { label: string; value: number; max?: number; title: string }) {
  const width = Math.max(2, Math.min(100, Math.abs(value) / max * 100))
  return <div title={title}><div className="mb-1 flex justify-between text-[11px] text-muted"><span>{label}</span><span>{value.toFixed(value < 2 ? 2 : 0)}</span></div><div className="h-1 rounded bg-white/5"><div className="h-1 rounded bg-mint" style={{ width: `${width}%` }} /></div></div>
}

function RecommendationCard({ recommendation, rank }: { recommendation: Recommendation; rank: number }) {
  const player = useDraftStore((state) => state.players.find((item) => item.id === recommendation.playerId))
  const draftPlayer = useDraftStore((state) => state.draftPlayer)
  const settings = useDraftStore((state) => state.settings)
  const picks = useDraftStore((state) => state.picks)
  if (!player) return null
  const onClockTeam = teamForPick(picks.length + 1, settings.teamCount)
  const destLabel = onClockTeam === settings.userTeam ? 'YOU' : `T${onClockTeam}`
  return <article className={`rounded-xl border p-4 ${rank === 0 ? 'border-mint/50 bg-mint/[.06] shadow-glow' : 'border-line bg-ink/35'}`}>
    <div className="flex items-start gap-3"><span className="grid h-7 w-7 place-items-center rounded-full bg-white/5 text-xs font-bold text-muted">{rank + 1}</span><div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-2"><h3 className="truncate font-semibold">{player.name}</h3><PositionPill position={player.position} /><span className={`rounded-full px-2 py-0.5 text-[9px] font-black tracking-wider ${recommendation.tierLabel === "CAN'T PASS" ? 'bg-lime text-ink' : 'bg-white/10 text-muted'}`}>{recommendation.tierLabel}</span></div>
      <p className="mt-1 text-xs leading-5 text-muted">{recommendation.explanation}</p>
    </div><div className="text-right"><div className="text-xl font-bold text-mint">{recommendation.dvsScore}</div><div className="text-[9px] uppercase tracking-wider text-muted">DVS</div></div></div>
    <details className="mt-3"><summary className="cursor-pointer text-xs font-semibold text-muted">Why this pick?</summary><div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
      <ScoreBar label="Marginal value" value={recommendation.breakdown.marginalValue} title="Immediate roster value from adding this player" />
      <ScoreBar label="Wait loss" value={recommendation.breakdown.waitLoss} max={30} title="Expected value lost if you pass and wait" />
      <ScoreBar label="Tier urgency" value={recommendation.breakdown.tierOpportunityCost ?? recommendation.breakdown.tierUrgency} max={10} title="Expert tier cliff combined with exhaustion risk" />
      <ScoreBar label="Survival chance" value={(recommendation.breakdown.adjustedSurvivalProbability ?? recommendation.breakdown.survivalProbability) * 100} title="Adjusted odds this player lasts until your next pick" />
      <ScoreBar label="Next-pick value" value={recommendation.breakdown.expectedNextPickValue ?? 0} title="Expected best value available on your next turn after this pick" />
      <ScoreBar label="Two-pick path" value={recommendation.breakdown.twoPickPathValue ?? recommendation.dvsScore} title="Combined immediate value plus expected next-pick opportunity" />
    </div></details>
    <button className="mt-4 w-full rounded-lg bg-mint/10 py-2 text-xs font-bold text-mint hover:bg-mint/20" onClick={() => void draftPlayer(player)}>Draft {player.name} · {destLabel}</button>
  </article>
}

function RosterPickRow({ pick, teamCount, onRemoveKeeper }: { pick: DraftPick; teamCount: number; onRemoveKeeper?: (id: string) => void }) {
  const roundLabel = pick.isKeeper ? 'R1' : `R${roundForPick(pick.pickNumber, teamCount)}`
  return <div className="group flex items-center gap-2 rounded bg-black/10 px-2 py-1.5 text-xs">
    <span className="w-6 shrink-0 font-mono text-[10px] text-muted">{roundLabel}</span>
    {pick.isKeeper && <span className="rounded bg-amber-300/20 px-1 text-[9px] font-bold text-amber-200" title="Keeper">K</span>}
    <PositionPill position={pick.position} />
    <span className="min-w-0 flex-1 truncate">{pick.playerName}</span>
    {pick.isKeeper && onRemoveKeeper && <button aria-label={`Remove keeper ${pick.playerName}`} title="Remove keeper" className="invisible shrink-0 text-xs text-rose-300 group-hover:visible focus:visible" onClick={() => void onRemoveKeeper(pick.id)}>×</button>}
  </div>
}

function RosterPickList({ roster, teamCount, onRemoveKeeper }: { roster: DraftPick[]; teamCount: number; onRemoveKeeper?: (id: string) => void }) {
  return <div className="space-y-1">{roster.map((pick) => <RosterPickRow key={pick.id} pick={pick} teamCount={teamCount} onRemoveKeeper={onRemoveKeeper} />)}{!roster.length && <p className="p-2 text-xs text-muted">No picks yet.</p>}</div>
}

function TeamLineup({ roster, rosterSlots }: { roster: DraftPick[]; rosterSlots: LeagueSettings['rosterSlots'] }) {
  const fills = assignRosterSlots(roster, rosterSlots)
  return <div className="space-y-1" data-testid="team-lineup">
    {fills.map((fill, index) => {
      const kindIndex = fills.slice(0, index).filter((row) => row.slot === fill.slot).length
      return <div key={`${fill.slot}-${index}`} data-testid={`roster-slot-${fill.slot}-${kindIndex}`} className="flex items-center gap-2 rounded bg-black/10 px-2 py-1.5 text-xs">
        <span className="w-9 shrink-0 font-mono text-[10px] font-bold text-muted">{SLOT_LABELS[fill.slot]}</span>
        {fill.pick
          ? <><PositionPill position={fill.pick.position} /><span className="truncate">{fill.pick.playerName}</span>{fill.pick.isKeeper && <span className="rounded bg-amber-300/20 px-1 text-[9px] font-bold text-amber-200">K</span>}</>
          : <span className="text-muted">—</span>}
      </div>
    })}
  </div>
}

function rosterBoardRowClass(isUser: boolean, isOnClock: boolean) {
  if (isUser && isOnClock) return 'border-mint/40 bg-mint/5 border-l-4 border-l-lime'
  if (isUser) return 'border-mint/40 bg-mint/5'
  if (isOnClock) return 'border-lime/50 bg-lime/[.06] shadow-[0_0_20px_rgba(198,245,111,.08)]'
  return 'border-line bg-ink/30'
}

export function Rosters() {
  const { picks, keepers, settings, removeKeeper } = useDraftStore()
  const [view, setView] = useState<'board' | 'team'>('board')
  const [selectedTeam, setSelectedTeam] = useState(settings.userTeam)

  useEffect(() => {
    setSelectedTeam((current) => Math.min(Math.max(1, current), settings.teamCount))
  }, [settings.userTeam, settings.teamCount])

  const openTeamView = (team: number) => {
    setSelectedTeam(team)
    setView('team')
  }

  const onClockTeam = teamForPick(picks.length + 1, settings.teamCount)
  const selectedRoster = rosterEntriesForTeam(picks, keepers, selectedTeam, settings.teamCount)

  return <section className="panel lg:col-span-3" data-testid="snake-board">
    <div className="panel-heading">
      <div>
        <p className="eyebrow">Snake board</p>
        <h2>League rosters {view === 'team' && <span className="font-normal text-muted">{selectedRoster.length} picks</span>}</h2>
      </div>
      <div className="flex gap-1" role="tablist" aria-label="Roster view">
        {(['board', 'team'] as const).map((item) => <button key={item} role="tab" aria-selected={view === item} data-testid={`roster-view-${item}`} onClick={() => setView(item)} className={`rounded-md px-2.5 py-1 text-[11px] font-bold capitalize ${view === item ? 'bg-mint text-ink' : 'text-muted hover:bg-white/5'}`}>{item}</button>)}
      </div>
    </div>
    {view === 'team' && <div className="flex gap-1 overflow-x-auto border-b border-line px-3 py-2" role="tablist" aria-label="Select team">
      {Array.from({ length: settings.teamCount }, (_, index) => index + 1).map((team) => {
        const isUser = team === settings.userTeam
        return <button key={team} role="tab" aria-selected={selectedTeam === team} data-testid={`roster-team-chip-${team}`} onClick={() => setSelectedTeam(team)} className={`shrink-0 rounded-md px-2.5 py-1 text-[11px] font-bold ${selectedTeam === team ? 'bg-mint text-ink' : isUser ? 'border border-mint/40 text-mint hover:bg-mint/5' : 'text-muted hover:bg-white/5'}`}>
          {isUser ? 'YOU' : `T${team}`}
        </button>
      })}
    </div>}
    <div className="max-h-[490px] overflow-auto p-3">
      {view === 'board' ? <div className="space-y-2">{Array.from({ length: settings.teamCount }, (_, index) => index + 1).map((team) => {
        const roster = rosterEntriesForTeam(picks, keepers, team, settings.teamCount)
        const latest = roster.at(-1)
        const isUser = team === settings.userTeam
        const isOnClock = team === onClockTeam
        return <details key={team} data-testid={`roster-team-${team}`} data-on-clock={isOnClock || undefined} open={isUser ? true : undefined} className={`rounded-lg border ${rosterBoardRowClass(isUser, isOnClock)}`}>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 p-3">
            <span className="text-xs font-semibold">Team {team} {isUser && <span className="ml-1 text-mint">YOU</span>}{isOnClock && <span className="ml-1 text-[10px] font-bold uppercase tracking-wide text-lime">ON CLOCK</span>}</span>
            <span className="flex min-w-0 items-center gap-2">
              <button type="button" data-testid={`view-team-${team}`} className="shrink-0 text-[10px] font-semibold text-mint hover:underline" onClick={(event) => { event.preventDefault(); openTeamView(team) }}>View roster</button>
              <span className="min-w-0 truncate text-right text-[10px] text-muted">
                {latest
                  ? <span className="inline-flex max-w-full items-center gap-1.5"><span className="font-mono">{latest.isKeeper ? 'R1' : `R${roundForPick(latest.pickNumber, settings.teamCount)}`}</span>{latest.isKeeper && <span className="font-bold text-amber-200">K</span>}<span className="truncate">{latest.playerName}</span></span>
                  : `${roster.length} picks`}
              </span>
            </span>
          </summary>
          <div className="border-t border-line/60 p-2"><RosterPickList roster={roster} teamCount={settings.teamCount} onRemoveKeeper={(id) => void removeKeeper(id)} /></div>
        </details>
      })}</div> : <div data-testid={`roster-team-detail-${selectedTeam}`}>
        <p className="mb-2 text-xs font-semibold">Team {selectedTeam} {selectedTeam === settings.userTeam && <span className="text-mint">YOU</span>}</p>
        <TeamLineup roster={selectedRoster} rosterSlots={settings.rosterSlots} />
      </div>}
    </div>
  </section>
}

function PickHistory({ onCorrect }: { onCorrect: (id: string) => void }) {
  const { picks, undoLastPick, removePick } = useDraftStore()
  return <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Audit trail</p><h2>Pick history</h2></div><button disabled={!picks.length} className="button-secondary !px-2 !py-1 text-xs disabled:opacity-40" onClick={() => void undoLastPick()}>↶ Undo last</button></div>
    <ol className="max-h-56 overflow-auto p-2">{[...picks].reverse().map((pick) => <li key={pick.id} className="group flex items-center gap-2 rounded-lg p-2 hover:bg-white/[.03]"><span className="w-8 text-right font-mono text-[10px] text-muted">{pick.pickNumber}</span><PositionPill position={pick.position} /><span className="min-w-0 flex-1 truncate text-xs">{pick.playerName}</span><span className="text-[10px] text-muted">T{pick.teamId}</span><button aria-label={`Correct ${pick.playerName} pick`} title="Replace player" className="invisible text-xs text-mint group-hover:visible focus:visible" onClick={() => onCorrect(pick.id)}>Edit</button><button aria-label={`Remove ${pick.playerName} pick`} title="Remove pick" className="invisible text-xs text-rose-300 group-hover:visible focus:visible" onClick={() => void removePick(pick.id)}>×</button></li>)}{!picks.length && <li className="p-7 text-center text-xs text-muted">Picks appear here as the draft unfolds.</li>}</ol>
  </section>
}

export default function App() {
  const { hydrate, hydrated, refreshRecommendations, loadBundledRankings, settings, players, adjustments, picks, keepers, recommendations, engineMode, engineWarning, offlineReady } = useDraftStore()
  const [modal, setModal] = useState<'setup' | 'import' | null>(null)
  const [correctionId, setCorrectionId] = useState<string>()
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => { void hydrate() }, [hydrate])
  useEffect(() => {
    const update = () => {
      setOnline(navigator.onLine)
      if (navigator.onLine) void refreshRecommendations()
    }
    window.addEventListener('online', update); window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [refreshRecommendations])
  const currentPick = picks.length + 1
  const round = Math.ceil(currentPick / settings.teamCount)
  const picksUntilTurn = Array.from(
    { length: settings.teamCount * 2 + 1 },
    (_, offset) => offset
  ).find((offset) => teamForPick(currentPick + offset, settings.teamCount) === settings.userTeam) ?? settings.teamCount
  const exportBackup = () => {
    const blob = new Blob(
      [JSON.stringify({ schemaVersion: 1, exportedAt: new Date().toISOString(), settings, players, adjustments, picks, keepers }, null, 2)],
      { type: 'application/json' }
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `fantasy-draft-backup-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
  }
  if (!hydrated) return <main className="grid min-h-screen place-items-center bg-ink text-mint">Opening your local draft room…</main>
  return <div className="min-h-screen bg-ink text-slate-100">
    <header className="sticky top-0 z-20 border-b border-line bg-ink/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-3 sm:px-6"><div className="grid h-9 w-9 place-items-center rounded-lg bg-mint font-black text-ink">F</div><div className="mr-auto"><h1 className="text-sm font-bold sm:text-base">Fantasy Draft Tool</h1><p className="hidden text-[10px] text-muted sm:block">{settings.name} · {settings.scoring.replace('_', ' ')} · Snake</p></div>
        <div data-testid="offline-status" data-ready={offlineReady} className={`flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-semibold ${offlineReady ? 'border-mint/30 text-mint' : 'border-amber-300/30 text-amber-200'}`}><span className={`h-1.5 w-1.5 rounded-full ${offlineReady ? 'bg-mint' : 'bg-amber-300'}`} /><span className="hidden sm:inline">{online ? (offlineReady ? 'ONLINE · OFFLINE READY' : 'ONLINE · PREPARING OFFLINE') : (offlineReady ? 'OFFLINE READY' : 'OFFLINE NOT READY')}</span><span className="sm:hidden">{offlineReady ? 'READY' : 'SETUP'}</span></div>
        <button className="button-secondary" onClick={exportBackup}>Export</button>
        <button
          className="button-secondary"
          title="Replace the player pool with the committed expert rankings. Does not fetch from the internet."
          onClick={() => {
            if (window.confirm('Replace the current player pool with the bundled expert rankings? Boosts, fades, and tags stay.')) {
              void loadBundledRankings()
            }
          }}
        >Load bundled rankings</button>
        <button className="button-secondary" onClick={() => setModal('import')}>Import CSV</button>
        <button className="button-secondary" onClick={() => setModal('setup')}>League setup</button>
      </div>
    </header>
    <main className="mx-auto max-w-[1600px] p-4 sm:p-6">
      <section className="mb-5 grid gap-3 rounded-2xl border border-line bg-gradient-to-r from-panel to-ink p-4 shadow-glow lg:grid-cols-[1fr_auto] lg:items-center">
        <div><div className="mb-2 flex items-center gap-3"><span className="rounded-md bg-lime px-2 py-1 text-[10px] font-black tracking-wider text-ink">{correctionId ? 'CORRECT PICK' : 'LIVE DRAFT'}</span><span className="text-xs text-muted">Round {round} · Pick {currentPick}</span></div><PickSearch correctionId={correctionId} onCorrectionDone={() => setCorrectionId(undefined)} /></div>
        <div className="flex items-center gap-5 lg:px-4"><div><p className="text-[10px] uppercase tracking-wider text-muted">Engine</p><p className="text-xs font-semibold text-mint">{engineMode === 'online-api' ? 'Cloud DVS' : engineMode === 'offline-python' ? 'Offline Python DVS' : 'Dev fallback'}</p></div><div className="h-8 w-px bg-line" /><div><p className="text-[10px] uppercase tracking-wider text-muted">Next turn</p><p className="text-xs font-semibold">{picksUntilTurn === 0 ? 'On the clock' : `${picksUntilTurn} picks away`}</p></div></div>
      </section>
      {engineWarning && <div role="status" className="mb-4 rounded-lg border border-amber-300/20 bg-amber-300/5 px-4 py-2 text-xs text-amber-100">{engineWarning}</div>}
      <div className="grid gap-4 lg:grid-cols-12">
        <section className="panel lg:col-span-4 lg:row-span-2"><div className="panel-heading"><div><p className="eyebrow">DVS engine</p><h2>Recommended now</h2></div><span className="text-xs text-muted">For your roster · pick goes to on-clock team</span></div><div className="max-h-[720px] space-y-3 overflow-auto p-3">{recommendations.slice(0, 6).map((recommendation, index) => <RecommendationCard key={recommendation.playerId} recommendation={recommendation} rank={index} />)}</div></section>
        <AvailablePlayers /><Rosters /><div className="lg:col-span-8"><PickHistory onCorrect={setCorrectionId} /></div>
      </div>
    </main>
    {modal === 'setup' && <SetupDialog close={() => setModal(null)} />}{modal === 'import' && <ImportDialog close={() => setModal(null)} />}
  </div>
}
