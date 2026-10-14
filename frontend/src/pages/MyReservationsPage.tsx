import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useCancel, useMyReservations, useResources, type Reservation } from '../api/queries'
import { errorMessage } from '../lib/messages'
import { DEFAULT_TIMEZONE, formatSlot } from '../lib/time'

export function MyReservationsPage() {
  const reservations = useMyReservations()
  const resources = useResources()
  const cancel = useCancel(false)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)
  // Re-evaluated each minute so a reservation moves to the history once it ends.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(id)
  }, [])

  const court = (id: string) => resources.data?.find((r) => r.id === id)
  const items = reservations.data?.items ?? []
  const upcoming = items
    .filter((r) => r.status === 'confirmed' && Date.parse(r.ends_at) > now)
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at))
  const history = items
    .filter((r) => !upcoming.includes(r))
    .sort((a, b) => Date.parse(b.starts_at) - Date.parse(a.starts_at))

  async function onCancel(reservation: Reservation) {
    setError(null)
    setCancelling(reservation.id)
    try {
      await cancel.mutateAsync(reservation.id)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setCancelling(null)
    }
  }

  const row = (r: Reservation, canCancel: boolean) => {
    const c = court(r.resource_id)
    return (
      <tr key={r.id} className="border-b border-rule align-middle">
        <th scope="row" className="py-3 pr-4 text-left font-semibold">
          {formatSlot(r.starts_at, r.ends_at, c?.timezone ?? DEFAULT_TIMEZONE)}
        </th>
        <td className="py-3 pr-4">{c?.name ?? '—'}</td>
        <td className="py-3 pr-4">{r.status === 'confirmed' ? 'Confirmada' : 'Cancelada'}</td>
        <td className="py-3 text-right">
          {canCancel && (
            <button
              type="button"
              className="btn"
              onClick={() => onCancel(r)}
              disabled={cancelling === r.id}
              aria-label={`Cancelar la reserva de ${c?.name ?? 'la cancha'}, ${formatSlot(r.starts_at, r.ends_at, c?.timezone ?? DEFAULT_TIMEZONE)}`}
            >
              {cancelling === r.id ? 'Cancelando…' : 'Cancelar'}
            </button>
          )}
        </td>
      </tr>
    )
  }

  const table = (title: string, list: Reservation[], canCancel: boolean, empty: React.ReactNode) => (
    <section className="mt-8">
      <h2 className="text-xl font-bold [font-stretch:90%]">{title}</h2>
      {list.length === 0 ? (
        <p className="mt-3 text-ink-soft">{empty}</p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-base">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr className="border-b-[1.5px] border-ink text-left text-sm">
                <th scope="col" className="py-2 pr-4 font-bold">Fecha y hora</th>
                <th scope="col" className="py-2 pr-4 font-bold">Cancha</th>
                <th scope="col" className="py-2 pr-4 font-bold">Estado</th>
                <th scope="col" className="py-2 text-right font-bold"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody>{list.map((r) => row(r, canCancel))}</tbody>
          </table>
        </div>
      )}
    </section>
  )

  return (
    <div>
      <h1 className="text-3xl font-bold leading-none tracking-tight [font-stretch:90%]">Mis reservas</h1>
      <p className="mt-2 text-sm text-ink-soft">
        Puedes cancelar hasta 12 horas antes del inicio.
      </p>

      <div aria-live="polite">
        {error && (
          <p role="alert" className="mt-4 border-y-[1.5px] border-signal py-2.5 font-semibold text-signal">
            {error}
          </p>
        )}
      </div>

      {reservations.isPending && <p role="status" className="mt-6 text-ink-soft">Cargando tus reservas…</p>}
      {reservations.isError && (
        <p role="alert" className="mt-6 font-semibold text-signal">No se pudieron cargar tus reservas.</p>
      )}
      {reservations.data && (
        <>
          {table(
            'Próximas',
            upcoming,
            true,
            <>
              No tienes reservas próximas.{' '}
              <Link to="/" className="font-semibold text-ink underline underline-offset-4">
                Ver el día y reservar
              </Link>
              .
            </>,
          )}
          {table('Historial', history, false, 'Aún no hay reservas pasadas ni canceladas.')}
          {reservations.data.total > items.length && (
            <p className="mt-4 text-sm text-ink-soft">
              Se muestran las últimas {items.length} de {reservations.data.total}.
            </p>
          )}
        </>
      )}
    </div>
  )
}
