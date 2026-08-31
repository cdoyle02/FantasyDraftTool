import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ADP_SOURCES, adpSourceMeta, type AdpSource, type SortDir } from './adp'

export function AdpSourceHeader({
  source,
  dir,
  onSourceChange,
  onToggleDir
}: {
  source: AdpSource
  dir: SortDir
  onSourceChange: (source: AdpSource) => void
  onToggleDir: () => void
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(() => ADP_SOURCES.findIndex((item) => item.key === source))
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 })
  const root = useRef<HTMLTableCellElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLUListElement>(null)
  const selected = adpSourceMeta(source)

  useEffect(() => {
    if (!open) return
    setActive(ADP_SOURCES.findIndex((item) => item.key === source))
    const place = () => {
      const rect = trigger.current?.getBoundingClientRect()
      if (!rect) return
      setMenuPos({ top: rect.bottom + 4, left: rect.left })
    }
    place()
    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node
      if (root.current?.contains(target) || menu.current?.contains(target)) return
      setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, source])

  const choose = (next: AdpSource) => {
    onSourceChange(next)
    setOpen(false)
  }

  return (
    <th ref={root} className="relative px-1 py-1.5 align-bottom">
      <div className="flex flex-col items-start gap-0.5">
        <button
          type="button"
          className="flex items-center gap-0.5 text-[10px] font-normal uppercase tracking-wider text-muted hover:text-white"
          onClick={onToggleDir}
          aria-label={`Sort by ${selected.label} ADP ${dir === 'asc' ? 'descending' : 'ascending'}`}
          title="Toggle ADP sort direction"
        >
          ADP
          <span className="text-mint" aria-hidden>{dir === 'asc' ? '▲' : '▼'}</span>
        </button>
        <button
          ref={trigger}
          type="button"
          className="flex items-center gap-0.5 rounded px-0.5 text-[10px] font-bold tracking-wider text-mint hover:bg-white/5"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={`ADP source, ${selected.label}`}
          title={`${selected.label} ADP`}
          onClick={() => setOpen((current) => !current)}
          onKeyDown={(event) => {
            if (!open && (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ')) {
              event.preventDefault()
              setOpen(true)
              return
            }
            if (!open) return
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setActive((index) => (index + 1) % ADP_SOURCES.length)
            }
            if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActive((index) => (index - 1 + ADP_SOURCES.length) % ADP_SOURCES.length)
            }
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              const item = ADP_SOURCES[active]
              if (item) choose(item.key)
            }
          }}
        >
          {selected.short}
          <span aria-hidden>▾</span>
        </button>
      </div>
      {open && createPortal(
        <ul
          ref={menu}
          role="menu"
          aria-label="ADP source"
          className="z-[60] min-w-[9.5rem] rounded-lg border border-line bg-panel py-1 shadow-2xl"
          style={{ position: 'fixed', top: menuPos.top, left: menuPos.left }}
        >
          {ADP_SOURCES.map((item, index) => {
            const isSelected = item.key === source
            return (
              <li key={item.key} role="none">
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={isSelected}
                  className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-[11px] font-semibold ${
                    index === active || isSelected ? 'bg-mint/10 text-white' : 'text-slate-200 hover:bg-white/5'
                  }`}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(item.key)}
                >
                  <span>{item.label}</span>
                  {isSelected && <span className="text-mint" aria-hidden>✓</span>}
                </button>
              </li>
            )
          })}
        </ul>,
        document.body
      )}
    </th>
  )
}
