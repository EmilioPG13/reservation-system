import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  useAdminDay,
  useAvailability,
  useBook,
  useCancel,
  useMyReservations,
  type AdminReservation,
} from '../api/queries'
import { useAuth } from '../auth/context'
import { CourtGrid } from '../grid/CourtGrid'
import { buildGrid, newlyTaken, slotKey, KIND_TEXT, type CellModel, type DayAvailability } from '../grid/model'
import { errorMessage, SLOT_TAKEN } from '../lib/messages'
import { addDays, DEFAULT_TIMEZONE, formatDay, formatSlot, isIsoDate, todayIn } from '../lib/time'

type Notice = { tone: 'ok' | 'error'; text: string }

export function DayPage({ admin = false }: { admin?: boolean }) {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const today = todayIn(DEFAULT_TIMEZONE)
  const requested = params.get('fecha')
  const date = isIsoDate(requested) ? requested : today

  const availability = useAvailability(date)
  const adminDay = useAdminDay(date, admin)
  const mine = useMyReservations()
  const book = useBook()
  const cancel = useCancel(admin)

  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [changed, setChanged] = useState<ReadonlySet<string>>(new Set())
  const [notice, setNotice] = useState<Notice | null>(null)
  const [slow, setSlow] = useState(false)

  const data = availability.data
  const model = useMemo(() => (data ? buildGrid(data, activeKey, admin) : null), [data, activeKey, admin])

  // After each poll, mark what someone else took meanwhile; if it was the open selection, say so.
  const previous = useRef<DayAvailability | undefined>(undefined)
  useEffect(() => {
    if (!data) return
    const taken = newlyTaken(previous.current, data)
    previous.current = data
    if (taken.length === 0) return
    setChanged((current) => new Set([...current, ...taken]))
    if (activeKey && taken.includes(activeKey)) {
      setActiveKey(null)
      setNotice({ tone: 'error', text: SLOT_TAKEN })
    }
  }, [data, activeKey])

  // A first load can be slow when the free-tier database was asleep; say so instead of hiding it.
  useEffect(() => {
    if (!availability.isPending) return
    const id = setTimeout(() => setSlow(true), 4000)
    return () => clearTimeout(id)
  }, [availability.isPending])

  const bookedBy = useMemo(() => {
    if (!admin || !adminDay.data) return undefined
    return new Map(
      adminDay.data
        .filter((r: AdminReservation) => r.status === 'confirmed')
        .map((r) => [slotKey(r.resource_id, r.starts_at), r.user_name] as const),
    )
  }, [admin, adminDay.data])

  const cells = useMemo(() => new Map(model?.rows.flatMap((r) => r.cells).map((c) => [c.key, c])), [model])
  const active = activeKey ? (cells.get(activeKey) ?? null) : null

  const changeDay = useCallback(
    (next: string) => {
      setParams(next === today ? {} : { fecha: next }, { replace: true })
      setActiveKey(null)
      setChanged(new Set())
      setNotice(null)
      previous.current = undefined
    },
    [setParams, today],
  )

  function onActivate(cell: CellModel) {
    setNotice(null)
    // Free cells toggle a selection; own (or, for admins, any) booked cells open their reservation.
    setActiveKey((key) => (cell.kind === 'libre' || cell.kind === 'seleccionada') && key === cell.key ? null : cell.key)
  }

  // The reservation behind a booked cell the panel is showing.
  const reservationId = useMemo(() => {
    if (!active?.slot || active.slot.status !== 'booked') return null
    const startMs = Date.parse(active.slot.start)
    if (admin) {
      return adminDay.data?.find(
        (r) => r.status === 'confirmed' && r.resource_id === active.courtId && Date.parse(r.starts_at) === startMs,
      )
    }
    return mine.data?.items.find(
      (r) => r.status === 'confirmed' && r.resource_id === active.courtId && Date.parse(r.starts_at) === startMs,
    )
  }, [active, admin, adminDay.data, mine.data])

  async function onBook() {
    if (!active?.slot) return
    const label = formatSlot(active.slot.start, active.slot.end, active.timeZone)
    try {
      await book.mutateAsync({ resourceId: active.courtId, startsAt: active.slot.start })
      setActiveKey(null)
      setNotice({ tone: 'ok', text: `Reserva confirmada: ${active.courtName}, ${label}. Te enviamos un correo.` })
    } catch (error) {
      const text = errorMessage(error)
      if (text === SLOT_TAKEN) setChanged((current) => new Set([...current, active.key]))
      setActiveKey(null)
      setNotice({ tone: 'error', text })
    }
  }

  async function onCancel() {
    if (!reservationId || !active?.slot) return
    const id = typeof reservationId === 'string' ? reservationId : reservationId.id
    try {
      await cancel.mutateAsync(id)
      setActiveKey(null)
      setNotice({ tone: 'ok', text: 'Reserva cancelada. El horario quedó libre.' })
    } catch (error) {
      setNotice({ tone: 'error', text: errorMessage(error) })
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <h1 className="text-2xl font-bold leading-none tracking-tight [font-stretch:90%] first-letter:uppercase sm:text-3xl">
            {formatDay(date)}
          </h1>
          <p className="mt-2 text-sm text-ink-soft">
            {admin ? 'Vista de administración: quién reservó cada horario.' : 'Elige un horario libre para reservar.'}
          </p>
        </div>
        <div className="flex items-center gap-2" role="group" aria-label="Cambiar de día">
          <button type="button" className="btn" onClick={() => changeDay(addDays(date, -1))} aria-label="Día anterior">
            <Arrow dir="left" /> <span className="hidden sm:inline">Anterior</span>
          </button>
          <button type="button" className="btn" onClick={() => changeDay(today)} disabled={date === today}>
            Hoy
          </button>
          <button type="button" className="btn" onClick={() => changeDay(addDays(date, 1))} aria-label="Día siguiente">
            <span className="hidden sm:inline">Siguiente</span> <Arrow dir="right" />
          </button>
        </div>
      </div>

      <Legend />

      <div aria-live="polite" className="min-h-0">
        {notice && (
          <p
            role={notice.tone === 'error' ? 'alert' : 'status'}
            className={`mb-3 border-y-[1.5px] py-2.5 font-semibold ${
              notice.tone === 'error' ? 'border-signal text-signal' : 'border-ink'
            }`}
          >
            {notice.text}
          </p>
        )}
      </div>

      {availability.isPending && (
        <div role="status" className="border-[1.5px] border-ink p-6">
          <p className="font-semibold">Cargando la jornada…</p>
          {slow && (
            <p className="mt-1 text-sm text-ink-soft">
              La base de datos estaba en reposo; tarda unos segundos en despertar. No cierres la página.
            </p>
          )}
        </div>
      )}

      {availability.isError && !data && (
        <div role="alert" className="border-[1.5px] border-signal p-6">
          <p className="font-semibold text-signal">No se pudo cargar la disponibilidad.</p>
          <button type="button" className="btn mt-3" onClick={() => availability.refetch()}>
            Reintentar
          </button>
        </div>
      )}

      {data && data.courts.length === 0 && (
        <div className="border-[1.5px] border-ink p-6">
          <p className="font-semibold">No hay canchas activas.</p>
          <p className="mt-1 text-sm text-ink-soft">
            {user?.role === 'admin' ? (
              <>
                Crea la primera en <Link to="/admin/canchas" className="font-semibold text-ink underline underline-offset-4">Canchas</Link>.
              </>
            ) : (
              'El club aún no ha publicado canchas.'
            )}
          </p>
        </div>
      )}

      {model && data && data.courts.length > 0 && (
        <CourtGrid
          model={model}
          changed={changed}
          bookedBy={bookedBy}
          onActivate={onActivate}
          onInteract={() => changed.size > 0 && setChanged(new Set())}
        />
      )}

      {active?.slot && (
        <>
          {/* The plate is fixed to the bottom edge; this spacer keeps it from covering the last row. */}
          <div aria-hidden="true" className="h-40 sm:h-24" />
          <section aria-label="Horario elegido" className="plate fixed inset-x-0 bottom-0 z-10 border-x-0 border-b-0">
            <div className="mx-auto flex max-w-[96rem] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
              <p className="font-semibold">
                {active.courtName} · {formatSlot(active.slot.start, active.slot.end, active.timeZone)}
                <span className="ml-2 font-normal opacity-80">{KIND_TEXT[active.kind]}</span>
              </p>
              {active.slot.status === 'available' ? (
                <div className="flex gap-2">
                  <button type="button" className="btn" onClick={() => setActiveKey(null)}>
                    Quitar selección
                  </button>
                  <button type="button" className="btn btn-plate" onClick={onBook} disabled={book.isPending}>
                    {book.isPending ? 'Reservando…' : 'Reservar'}
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button type="button" className="btn" onClick={() => setActiveKey(null)}>
                    Cerrar
                  </button>
                  <button type="button" className="btn btn-plate" onClick={onCancel} disabled={!reservationId || cancel.isPending}>
                    {cancel.isPending ? 'Cancelando…' : 'Cancelar reserva'}
                  </button>
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function Arrow({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d={dir === 'left' ? 'M14 8H2M7 3 2 8l5 5' : 'M2 8h12M9 3l5 5-5 5'} />
    </svg>
  )
}

/** The key to the marks, so the grid reads without guessing. */
function Legend() {
  const items = ['libre', 'ocupada', 'no-disponible', 'tuya', 'seleccionada'] as const
  return (
    <ul aria-label="Leyenda" className="my-4 flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {items.map((kind) => (
        <li key={kind} data-kind={kind} className="flex items-center gap-1.5">
          <span className="mark" aria-hidden="true" />
          {KIND_TEXT[kind]}
        </li>
      ))}
    </ul>
  )
}
