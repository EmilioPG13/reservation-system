import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'

type Mode = 'login' | 'register'

const COPY = {
  login: {
    title: 'Entrar',
    submit: 'Entrar',
    other: { text: '¿No tienes cuenta?', link: 'Crear una cuenta', to: '/registro' },
  },
  register: {
    title: 'Crear cuenta',
    submit: 'Crear cuenta',
    other: { text: '¿Ya tienes cuenta?', link: 'Entrar', to: '/entrar' },
  },
} as const

/** A fixed, made-up morning that teaches the five states. Marked as an example, never real data. */
const SAMPLE: { court: string; cells: [string, string][] }[] = [
  { court: 'Cancha 1', cells: [['libre', 'Libre'], ['ocupada', 'Ocupada'], ['ocupada', 'Ocupada'], ['libre', 'Libre'], ['libre', 'Libre']] },
  { court: 'Cancha 2', cells: [['no-disponible', 'No disponible'], ['libre', 'Libre'], ['tuya', 'Tuya'], ['libre', 'Libre'], ['ocupada', 'Ocupada']] },
  { court: 'Cancha 3', cells: [['libre', 'Libre'], ['libre', 'Libre'], ['seleccionada', 'Seleccionada'], ['ocupada', 'Ocupada'], ['libre', 'Libre']] },
]

function SampleDay() {
  return (
    <figure className="hidden lg:block" aria-hidden="true">
      <div className="grid-scroller" style={{ maxHeight: 'none', overflow: 'visible' }}>
        <div className="grid-table" style={{ '--cols': 5 } as React.CSSProperties}>
          <div className="grid-row">
            <div className="grid-head grid-corner" />
            {['09', '10', '11', '12', '13'].map((h) => (
              <div key={h} className="grid-head">
                {h}
                <span className="minutes">:00</span>
              </div>
            ))}
          </div>
          {SAMPLE.map((row) => (
            <div key={row.court} className="grid-row">
              <div className="grid-court">{row.court}</div>
              {row.cells.map(([kind, word], i) => (
                <div key={i} className="grid-cell" data-kind={kind}>
                  <span className="cell-line">
                    <span className="mark" />
                    <span>{word}</span>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <figcaption className="mt-3 text-sm text-ink-soft">
        Ejemplo ilustrativo. Un horario ocupado no se puede reservar otra vez.
      </figcaption>
    </figure>
  )
}

export function AuthPage({ mode }: { mode: Mode }) {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as { from?: string; expired?: boolean } | null
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const copy = COPY[mode]

  if (user) return <Navigate to={state?.from ?? '/'} replace />

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email')).trim()
    const password = String(form.get('password'))
    setBusy(true)
    setError(null)
    const failure =
      mode === 'login' ? await login(email, password) : await register(String(form.get('name')).trim(), email, password)
    setBusy(false)
    if (failure) setError(failure)
    else navigate(state?.from ?? '/', { replace: true })
  }

  return (
    <main className="mx-auto min-h-dvh max-w-[96rem] border-t-[6px] border-ink px-4 py-8 sm:px-6">
      <p className="text-xl font-bold tracking-tight [font-stretch:90%]">Court Booking</p>
      <div className="mt-12 grid gap-16 lg:grid-cols-[22rem_1fr]">
      <div className="max-w-sm">
        <h1 className="text-3xl font-bold leading-none tracking-tight [font-stretch:90%]">{copy.title}</h1>
        <p className="mt-3 text-ink-soft">Reserva tu cancha de pádel: ve todo el día de un vistazo.</p>

        {state?.expired && !error && (
          <p role="status" className="mt-6 border-y border-ink py-3 font-semibold">
            Tu sesión terminó. Entra de nuevo.
          </p>
        )}
        {error && (
          <p role="alert" className="mt-6 border-y-[1.5px] border-signal py-3 font-semibold text-signal">
            {error}
          </p>
        )}

        <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5" noValidate={false}>
          {mode === 'register' && (
            <label className="flex flex-col gap-1.5 font-semibold">
              Nombre
              <input name="name" type="text" required maxLength={100} autoComplete="name" className="field font-normal" />
            </label>
          )}
          <label className="flex flex-col gap-1.5 font-semibold">
            Correo
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              className="field font-normal"
              aria-invalid={error ? true : undefined}
            />
          </label>
          <label className="flex flex-col gap-1.5 font-semibold">
            Contraseña
            <input
              name="password"
              type="password"
              required
              minLength={mode === 'register' ? 8 : undefined}
              maxLength={128}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="field font-normal"
              aria-invalid={error ? true : undefined}
              aria-describedby={mode === 'register' ? 'pw-hint' : undefined}
            />
            {mode === 'register' && (
              <span id="pw-hint" className="text-sm font-normal text-ink-soft">
                Mínimo 8 caracteres.
              </span>
            )}
          </label>
          <button type="submit" disabled={busy} className="btn btn-plate mt-1">
            {busy ? 'Un momento…' : copy.submit}
          </button>
        </form>

        <p className="mt-8 text-sm text-ink-soft">
          {copy.other.text}{' '}
          <Link to={copy.other.to} state={state} className="font-semibold text-ink underline underline-offset-4">
            {copy.other.link}
          </Link>
        </p>
      </div>
      <SampleDay />
      </div>
    </main>
  )
}
