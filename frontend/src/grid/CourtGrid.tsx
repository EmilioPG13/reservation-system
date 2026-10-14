import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { formatHour } from '../lib/time'
import { cellLabel, KIND_TEXT, visibleRange, type CellModel, type GridModel } from './model'

type Props = {
  model: GridModel
  changed: ReadonlySet<string>
  /** Admin day view: who holds each booked slot, by cell key. */
  bookedBy?: ReadonlyMap<string, string>
  onActivate: (cell: CellModel) => void
  /** Any pointer or key use inside the grid; clears the "just taken" marks. */
  onInteract?: () => void
}

type Pos = { row: number; col: number }

/** "09:00" with the hour set large and the minutes quiet; the accessible name stays "09:00". */
function HourLabel({ text }: { text: string }) {
  const [hour, minutes] = text.split(':')
  return (
    <span>
      {hour}
      <span className="minutes">:{minutes}</span>
    </span>
  )
}

/** The one tab stop: where the user last was, else the first cell they can act on. */
function tabStop(rows: GridModel['rows'], pos: Pos | null): Pos {
  if (pos && rows[pos.row]?.cells[pos.col]) return pos
  for (let r = 0; r < rows.length; r++) {
    const c = rows[r].cells.findIndex((cell) => cell.actionable)
    if (c >= 0) return { row: r, col: c }
  }
  return { row: 0, col: 0 }
}

/**
 * A courts x hours grid following the ARIA grid pattern: one tab stop (roving tabindex),
 * arrows move between cells, Enter or Space activate. The scroller snaps to whole hours.
 */
export function CourtGrid({ model, changed, bookedBy, onActivate, onInteract }: Props) {
  const { rows, columns, timeZone } = model
  const refs = useRef(new Map<string, HTMLDivElement>())
  const scroller = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<Pos | null>(null)
  const [guide, setGuide] = useState('')

  const current = tabStop(rows, pos)

  const focusCell = useCallback(
    (next: Pos) => {
      const r = Math.max(0, Math.min(next.row, rows.length - 1))
      const c = Math.max(0, Math.min(next.col, columns.length - 1))
      setPos({ row: r, col: c })
      refs.current.get(rows[r].cells[c].key)?.focus()
    },
    [rows, columns.length],
  )

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>, cell: CellModel, at: Pos) => {
    onInteract?.()
    const moves: Record<string, Pos> = {
      ArrowRight: { row: at.row, col: at.col + 1 },
      ArrowLeft: { row: at.row, col: at.col - 1 },
      ArrowDown: { row: at.row + 1, col: at.col },
      ArrowUp: { row: at.row - 1, col: at.col },
      Home: event.ctrlKey ? { row: 0, col: 0 } : { row: at.row, col: 0 },
      End: event.ctrlKey
        ? { row: rows.length - 1, col: columns.length - 1 }
        : { row: at.row, col: columns.length - 1 },
    }
    if (event.key in moves) {
      event.preventDefault()
      focusCell(moves[event.key])
    } else if ((event.key === 'Enter' || event.key === ' ') && cell.actionable) {
      event.preventDefault()
      onActivate(cell)
    }
  }

  // Sticky guide: the first and last hour in view, recomputed while scrolling.
  const updateGuide = useCallback(() => {
    const el = scroller.current
    const sample = el?.querySelector<HTMLElement>('[data-col="0"]')
    const corner = el?.querySelector<HTMLElement>('.grid-corner')
    // No measured width yet (hidden or not laid out): nothing to guide.
    if (!el || !sample || !corner || sample.offsetWidth === 0) return
    // Nothing to scroll: the whole day is in view, whatever rounding says about the widths.
    if (el.scrollWidth <= el.clientWidth + 1) {
      setGuide(visibleRange(columns, 0, columns.length - 1, timeZone))
      return
    }
    // Otherwise count whole columns from real (fractional) widths.
    const width = sample.getBoundingClientRect().width
    const first = Math.round(el.scrollLeft / width)
    const count = Math.max(1, Math.floor((el.clientWidth - corner.getBoundingClientRect().width + 1) / width))
    setGuide(visibleRange(columns, first, first + count - 1, timeZone))
  }, [columns, timeZone])

  useEffect(updateGuide, [updateGuide])
  useEffect(() => {
    window.addEventListener('resize', updateGuide)
    return () => window.removeEventListener('resize', updateGuide)
  }, [updateGuide])

  return (
    <div
      ref={scroller}
      className="grid-scroller scroller"
      onScroll={updateGuide}
      onPointerDown={onInteract}
      tabIndex={-1}
    >
      <div
        role="grid"
        aria-label="Disponibilidad de canchas del día"
        aria-rowcount={rows.length + 1}
        aria-colcount={columns.length + 1}
        className="grid-table"
        style={{ '--cols': columns.length } as React.CSSProperties}
      >
        <div role="row" className="grid-row">
          <div role="columnheader" className="grid-head grid-corner">
            <span className="sr-only">Cancha</span>
            <span aria-hidden="true" className="text-ink-soft text-xs font-semibold">
              {guide}
            </span>
          </div>
          {columns.map((start, c) => (
            <div key={start} role="columnheader" data-col={c} className="grid-head">
              <HourLabel text={formatHour(start, timeZone)} />
            </div>
          ))}
        </div>
        {rows.map((row, r) => (
          <div key={row.courtId} role="row" className="grid-row">
            <div role="rowheader" className="grid-court">
              {row.courtName}
            </div>
            {row.cells.map((cell, c) => {
              const isChanged = changed.has(cell.key)
              const who = bookedBy?.get(cell.key)
              const tabbable = current.row === r && current.col === c
              return (
                <div
                  key={cell.key}
                  role="gridcell"
                  ref={(el) => {
                    if (el) refs.current.set(cell.key, el)
                    else refs.current.delete(cell.key)
                  }}
                  tabIndex={tabbable ? 0 : -1}
                  aria-label={cellLabel(cell, { changed: isChanged, bookedBy: who })}
                  aria-selected={cell.kind === 'seleccionada' ? true : undefined}
                  aria-disabled={cell.actionable ? undefined : true}
                  data-kind={cell.kind}
                  data-actionable={cell.actionable}
                  data-changed={isChanged || undefined}
                  className="grid-cell"
                  onFocus={() => setPos({ row: r, col: c })}
                  onClick={() => {
                    onInteract?.()
                    setPos({ row: r, col: c })
                    if (cell.actionable) onActivate(cell)
                  }}
                  onKeyDown={(e) => onKeyDown(e, cell, { row: r, col: c })}
                >
                  <span className="cell-line">
                    <span className="mark" aria-hidden="true" />
                    <span>{KIND_TEXT[cell.kind]}</span>
                  </span>
                  {isChanged && (
                    <span className="cell-note" data-signal="true">
                      Nueva
                    </span>
                  )}
                  {who && !isChanged && <span className="cell-note">{who}</span>}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
