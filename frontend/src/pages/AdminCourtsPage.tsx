import { useState, type FormEvent } from 'react'
import {
  useAdminMutations,
  useAdminResources,
  useBlackouts,
  type Resource,
} from '../api/queries'
import { errorMessage } from '../lib/messages'
import { DEFAULT_TIMEZONE, formatSlot, zonedToUtc } from '../lib/time'

// 24-hour half-hour choices: a time input follows the browser's locale and shows AM/PM.
const TIMES = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`)

function TimeSelect({ label, value, disabled, onChange }: { label: string; value: string; disabled: boolean; onChange: (v: string) => void }) {
  return (
    <select aria-label={label} className="field" disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)}>
      {!TIMES.includes(value) && <option value={value}>{value}</option>}
      {TIMES.map((t) => (
        <option key={t} value={t}>{t}</option>
      ))}
    </select>
  )
}

const WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

export function AdminCourtsPage() {
  const courts = useAdminResources()
  const mutations = useAdminMutations()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  const list = courts.data ?? []
  const selected = list.find((c) => c.id === selectedId) ?? list[0] ?? null

  async function run<T>(action: Promise<T>): Promise<boolean> {
    setError(null)
    setSaved(null)
    try {
      await action
      return true
    } catch (e) {
      setError(errorMessage(e))
      return false
    }
  }

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const ok = await run(
      mutations.createCourt.mutateAsync({
        name: String(data.get('name')).trim(),
        slot_minutes: Number(data.get('slot_minutes')),
        timezone: DEFAULT_TIMEZONE,
      }),
    )
    if (ok) form.reset()
  }

  return (
    <div>
      <h1 className="text-3xl font-bold leading-none tracking-tight [font-stretch:90%]">Canchas</h1>
      <p className="mt-2 text-sm text-ink-soft">Datos, horario semanal y bloqueos por mantenimiento.</p>

      <div aria-live="polite">
        {error && (
          <p role="alert" className="mt-4 border-y-[1.5px] border-signal py-2.5 font-semibold text-signal">
            {error}
          </p>
        )}
        {saved && !error && <p role="status" className="mt-4 border-y-[1.5px] border-ink py-2.5 font-semibold">{saved}</p>}
      </div>

      {courts.isPending && <p role="status" className="mt-6 text-ink-soft">Cargando canchas…</p>}

      <div className="mt-6 grid gap-8 lg:grid-cols-[18rem_1fr]">
        <div>
          <h2 className="text-xl font-bold [font-stretch:90%]">Todas</h2>
          {list.length === 0 && courts.data && <p className="mt-2 text-ink-soft">Aún no hay canchas. Crea la primera.</p>}
          <ul className="mt-2 border-t-[1.5px] border-ink">
            {list.map((court) => (
              <li key={court.id} className="border-b border-rule">
                <button
                  type="button"
                  onClick={() => setSelectedId(court.id)}
                  aria-current={selected?.id === court.id ? 'true' : undefined}
                  className={`flex min-h-11 w-full items-center justify-between px-2 text-left font-semibold hover:bg-wash ${
                    selected?.id === court.id ? 'bg-wash' : ''
                  }`}
                >
                  {court.name}
                  <span className="text-sm font-normal text-ink-soft">{court.active ? 'Activa' : 'Inactiva'}</span>
                </button>
              </li>
            ))}
          </ul>

          <form onSubmit={onCreate} className="mt-6 flex flex-col gap-3">
            <h3 className="text-base font-bold">Nueva cancha</h3>
            <label className="flex flex-col gap-1.5 font-semibold">
              Nombre
              <input name="name" required maxLength={100} className="field font-normal" />
            </label>
            <label className="flex flex-col gap-1.5 font-semibold">
              Minutos por franja
              <input name="slot_minutes" type="number" required min={5} max={480} defaultValue={60} className="field font-normal" />
            </label>
            <button type="submit" className="btn" disabled={mutations.createCourt.isPending}>
              Crear cancha
            </button>
          </form>
        </div>

        {selected && (
          <CourtEditor
            key={selected.id}
            court={selected}
            onSave={(body) => run(mutations.updateCourt.mutateAsync({ id: selected.id, body }))}
            onSaveHours={(hours) => run(mutations.setHours.mutateAsync({ id: selected.id, hours }))}
            onCreateBlackout={(body) => run(mutations.createBlackout.mutateAsync({ id: selected.id, body }))}
            onDeleteBlackout={(blackoutId) =>
              run(mutations.deleteBlackout.mutateAsync({ resourceId: selected.id, blackoutId }))
            }
            onSaved={setSaved}
          />
        )}
      </div>
    </div>
  )
}

type HoursRow = { open: boolean; from: string; to: string }

function CourtEditor({
  court,
  onSave,
  onSaveHours,
  onCreateBlackout,
  onDeleteBlackout,
  onSaved,
}: {
  court: Resource
  onSave: (body: { name: string; slot_minutes: number; active: boolean }) => Promise<boolean>
  onSaveHours: (hours: { weekday: number; open_time: string; close_time: string }[]) => Promise<boolean>
  onCreateBlackout: (body: { starts_at: string; ends_at: string; reason: string | null }) => Promise<boolean>
  onDeleteBlackout: (id: string) => Promise<boolean>
  onSaved: (message: string) => void
}) {
  const blackouts = useBlackouts(court.id)
  const [hours, setHours] = useState<HoursRow[]>(() =>
    WEEKDAYS.map((_, weekday) => {
      const h = court.opening_hours.find((x) => x.weekday === weekday)
      return { open: Boolean(h), from: h?.open_time.slice(0, 5) ?? '08:00', to: h?.close_time.slice(0, 5) ?? '22:00' }
    }),
  )

  const flash = onSaved

  async function onDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const ok = await onSave({
      name: String(data.get('name')).trim(),
      slot_minutes: Number(data.get('slot_minutes')),
      active: data.get('active') === 'on',
    })
    if (ok) flash('Datos guardados.')
  }

  async function onHours(event: FormEvent) {
    event.preventDefault()
    const ok = await onSaveHours(
      hours.flatMap((h, weekday) => (h.open ? [{ weekday, open_time: h.from, close_time: h.to }] : [])),
    )
    if (ok) flash('Horario guardado.')
  }

  async function onBlackout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(event.currentTarget)
    const reason = String(data.get('reason')).trim()
    const ok = await onCreateBlackout({
      starts_at: zonedToUtc(`${data.get('startsDate')}T${data.get('startsTime')}`, court.timezone),
      ends_at: zonedToUtc(`${data.get('endsDate')}T${data.get('endsTime')}`, court.timezone),
      reason: reason || null,
    })
    if (ok) {
      form.reset()
      flash('Bloqueo creado. Las reservas que ya existían en esa ventana siguen vigentes: cancélalas desde la vista del día.')
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <section aria-labelledby="datos">
        <h2 id="datos" className="text-xl font-bold [font-stretch:90%]">{court.name}</h2>
        <form onSubmit={onDetails} className="mt-3 flex max-w-md flex-col gap-4">
          <label className="flex flex-col gap-1.5 font-semibold">
            Nombre
            <input name="name" required maxLength={100} defaultValue={court.name} className="field font-normal" />
          </label>
          <label className="flex flex-col gap-1.5 font-semibold">
            Minutos por franja
            <input name="slot_minutes" type="number" required min={5} max={480} defaultValue={court.slot_minutes} className="field font-normal" />
          </label>
          <label className="flex min-h-11 items-center gap-3 font-semibold">
            <input name="active" type="checkbox" defaultChecked={court.active} className="size-5 accent-ink" />
            Activa (aparece en la cuadrícula)
          </label>
          <p className="text-sm text-ink-soft">Zona horaria: {court.timezone}</p>
          <button type="submit" className="btn self-start">Guardar datos</button>
        </form>
      </section>

      <section aria-labelledby="horario">
        <h2 id="horario" className="text-xl font-bold [font-stretch:90%]">Horario semanal</h2>
        <p className="mt-1 text-sm text-ink-soft">Un día sin horario queda cerrado. Horas en la zona de la cancha.</p>
        <form onSubmit={onHours} className="mt-3">
          <table className="w-full max-w-lg border-collapse">
            <thead>
              <tr className="border-b-[1.5px] border-ink text-left text-sm">
                <th scope="col" className="py-2 font-bold">Día</th>
                <th scope="col" className="py-2 font-bold">Abre</th>
                <th scope="col" className="py-2 font-bold">Cierra</th>
              </tr>
            </thead>
            <tbody>
              {WEEKDAYS.map((day, i) => (
                <tr key={day} className="border-b border-rule">
                  <th scope="row" className="py-1 text-left font-semibold">
                    <label className="flex min-h-11 items-center gap-3">
                      <input
                        type="checkbox"
                        className="size-5 accent-ink"
                        checked={hours[i].open}
                        onChange={(e) => setHours((h) => h.map((x, j) => (j === i ? { ...x, open: e.target.checked } : x)))}
                      />
                      {day}
                    </label>
                  </th>
                  <td className="py-1 pr-2">
                    <TimeSelect label={`${day}: abre`} disabled={!hours[i].open} value={hours[i].from} onChange={(v) => setHours((h) => h.map((x, j) => (j === i ? { ...x, from: v } : x)))} />
                  </td>
                  <td className="py-1">
                    <TimeSelect label={`${day}: cierra`} disabled={!hours[i].open} value={hours[i].to} onChange={(v) => setHours((h) => h.map((x, j) => (j === i ? { ...x, to: v } : x)))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="submit" className="btn mt-4">Guardar horario</button>
        </form>
      </section>

      <section aria-labelledby="bloqueos">
        <h2 id="bloqueos" className="text-xl font-bold [font-stretch:90%]">Bloqueos por mantenimiento</h2>
        {blackouts.isPending && <p role="status" className="mt-2 text-ink-soft">Cargando bloqueos…</p>}
        {blackouts.data && blackouts.data.length === 0 && <p className="mt-2 text-ink-soft">Sin bloqueos.</p>}
        {blackouts.data && blackouts.data.length > 0 && (
          <ul className="mt-2 max-w-xl border-t-[1.5px] border-ink">
            {blackouts.data.map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-3 border-b border-rule py-2">
                <span>
                  <span className="font-semibold">{formatSlot(b.starts_at, b.ends_at, court.timezone)}</span>
                  {b.reason && <span className="ml-2 text-ink-soft">{b.reason}</span>}
                </span>
                <button type="button" className="btn" onClick={() => onDeleteBlackout(b.id)} aria-label={`Quitar el bloqueo de ${formatSlot(b.starts_at, b.ends_at, court.timezone)}`}>
                  Quitar
                </button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={onBlackout} className="mt-5 flex max-w-xl flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <fieldset className="flex flex-col gap-1.5">
              <legend className="mb-1.5 font-semibold">Desde</legend>
              <div className="flex gap-2">
                <input name="startsDate" type="date" required aria-label="Desde: fecha" className="field font-normal" />
                <select name="startsTime" aria-label="Desde: hora" defaultValue="08:00" className="field w-auto font-normal">
                  {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5">
              <legend className="mb-1.5 font-semibold">Hasta</legend>
              <div className="flex gap-2">
                <input name="endsDate" type="date" required aria-label="Hasta: fecha" className="field font-normal" />
                <select name="endsTime" aria-label="Hasta: hora" defaultValue="22:00" className="field w-auto font-normal">
                  {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </fieldset>
          </div>
          <label className="flex flex-col gap-1.5 font-semibold">
            Motivo (opcional)
            <input name="reason" maxLength={200} className="field font-normal" />
          </label>
          <button type="submit" className="btn self-start">Crear bloqueo</button>
        </form>
      </section>
    </div>
  )
}
