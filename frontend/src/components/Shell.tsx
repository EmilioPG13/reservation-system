import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/context'

const link = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-11 shrink-0 items-center border-b-[3px] px-1 text-base font-semibold whitespace-nowrap ${
    isActive ? 'border-ink' : 'border-transparent text-ink-soft hover:text-ink'
  }`

/** The top rule of the page: name, the screens the user may open, and who is signed in. */
export function Shell() {
  const { user, logout } = useAuth()
  return (
    <>
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-ink focus:p-3 focus:text-paper">
        Saltar al contenido
      </a>
      <header className="border-y-[1.5px] border-t-[6px] border-ink bg-paper">
        <div className="mx-auto flex max-w-[96rem] flex-wrap items-end gap-x-6 gap-y-1 px-4 pt-3 sm:px-6">
          <p className="order-1 pb-2 text-xl font-bold tracking-tight [font-stretch:90%] sm:flex-1">Court Booking</p>
          <nav aria-label="Principal" className="order-3 flex w-full flex-wrap gap-x-4 sm:order-2 sm:w-auto sm:gap-x-5">
            <NavLink to="/" end className={link}>
              Reservar
            </NavLink>
            <NavLink to="/reservas" className={link}>
              Mis reservas
            </NavLink>
            {user?.role === 'admin' && (
              <>
                <NavLink to="/admin" end className={link}>
                  Admin
                </NavLink>
                <NavLink to="/admin/canchas" className={link}>
                  Canchas
                </NavLink>
              </>
            )}
          </nav>
          <div className="order-2 ml-auto flex items-center gap-3 pb-1 text-sm sm:order-3 sm:ml-0 sm:flex-1 sm:justify-end">
            <span className="hidden text-ink-soft sm:inline">{user?.name}</span>
            <button type="button" onClick={logout} className="btn min-h-11 px-3 text-sm" aria-label={`Salir (${user?.name ?? ""})`}>
              Salir
            </button>
          </div>
        </div>
      </header>
      <main id="contenido" className="mx-auto max-w-[96rem] px-4 py-5 sm:px-6">
        <Outlet />
      </main>
    </>
  )
}

/** Sends anonymous visitors to the login; `adminOnly` also turns away regular users. */
export function RequireAuth({ adminOnly = false }: { adminOnly?: boolean }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="p-6 text-ink-soft" role="status">Comprobando tu sesión…</p>
  if (!user) return <Navigate to="/entrar" replace state={{ from: location.pathname + location.search }} />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/" replace />
  return <Shell />
}
