import { Route, Routes } from 'react-router-dom'
import { RequireAuth } from './components/Shell'
import { AdminCourtsPage } from './pages/AdminCourtsPage'
import { AuthPage } from './pages/AuthPage'
import { DayPage } from './pages/DayPage'
import { MyReservationsPage } from './pages/MyReservationsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<AuthPage mode="login" />} />
      <Route path="/registro" element={<AuthPage mode="register" />} />
      <Route element={<RequireAuth />}>
        <Route index element={<DayPage />} />
        <Route path="/reservas" element={<MyReservationsPage />} />
      </Route>
      <Route element={<RequireAuth adminOnly />}>
        <Route path="/admin" element={<DayPage admin />} />
        <Route path="/admin/canchas" element={<AdminCourtsPage />} />
      </Route>
      <Route path="*" element={<p className="p-6">No encontramos esa página.</p>} />
    </Routes>
  )
}
