import type { Player } from '../types'

const positionStyle: Record<Player['position'], string> = {
  QB: 'bg-violet-400/15 text-violet-300',
  RB: 'bg-cyan-400/15 text-cyan-300',
  WR: 'bg-amber-300/15 text-amber-200',
  TE: 'bg-rose-400/15 text-rose-300',
  K: 'bg-slate-400/15 text-slate-300',
  DST: 'bg-blue-400/15 text-blue-300'
}

export function PositionPill({ position }: { position: Player['position'] }) {
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${positionStyle[position]}`}>{position}</span>
}
