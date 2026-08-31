import type { DraftPick, LeagueSettings, PlayerPosition, Position } from '../types'

export type RosterSlotKind = Position | 'BENCH'

export interface RosterSlotFill {
  slot: RosterSlotKind
  pick?: DraftPick
}

const STARTER_ORDER: RosterSlotKind[] = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPERFLEX', 'DST', 'K']
const FLEX_ELIGIBLE: PlayerPosition[] = ['RB', 'WR', 'TE']
const SUPERFLEX_ELIGIBLE: PlayerPosition[] = ['QB', 'RB', 'WR', 'TE']

export const SLOT_LABELS: Record<RosterSlotKind, string> = {
  QB: 'QB',
  RB: 'RB',
  WR: 'WR',
  TE: 'TE',
  FLEX: 'FLEX',
  SUPERFLEX: 'SF',
  DST: 'DST',
  K: 'K',
  BENCH: 'BN'
}

export function expandRosterSlots(rosterSlots: LeagueSettings['rosterSlots']): RosterSlotKind[] {
  return ([...STARTER_ORDER, 'BENCH'] as RosterSlotKind[]).flatMap((slot) =>
    Array.from({ length: Math.max(0, rosterSlots[slot] ?? 0) }, (): RosterSlotKind => slot)
  )
}

function firstOpenSlot(slots: RosterSlotKind[], filled: Array<DraftPick | undefined>, match: (slot: RosterSlotKind) => boolean) {
  return slots.findIndex((slot, index) => !filled[index] && match(slot))
}

export function assignRosterSlots(picks: DraftPick[], rosterSlots: LeagueSettings['rosterSlots']): RosterSlotFill[] {
  const slots = expandRosterSlots(rosterSlots)
  const filled: Array<DraftPick | undefined> = Array.from({ length: slots.length })
  const ordered = [...picks].sort((a, b) => a.pickNumber - b.pickNumber)

  for (const pick of ordered) {
    const direct = firstOpenSlot(slots, filled, (slot) => slot === pick.position)
    const flex = FLEX_ELIGIBLE.includes(pick.position)
      ? firstOpenSlot(slots, filled, (slot) => slot === 'FLEX')
      : -1
    const superflex = SUPERFLEX_ELIGIBLE.includes(pick.position)
      ? firstOpenSlot(slots, filled, (slot) => slot === 'SUPERFLEX')
      : -1
    const bench = firstOpenSlot(slots, filled, (slot) => slot === 'BENCH')
    const index = [direct, flex, superflex, bench].find((candidate) => candidate >= 0) ?? -1
    if (index >= 0) {
      filled[index] = pick
      continue
    }
    slots.push('BENCH')
    filled.push(pick)
  }

  return slots.map((slot, index) => ({ slot, pick: filled[index] }))
}
