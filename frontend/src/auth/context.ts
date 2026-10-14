import { createContext, useContext } from 'react'
import type { components } from '../api/schema'

export type User = components['schemas']['UserRead']

export type AuthState = {
  user: User | null
  /** True until the stored token (if any) has been checked against the API. */
  loading: boolean
  /** Each resolves to an error message in Spanish, or null on success. */
  login: (email: string, password: string) => Promise<string | null>
  register: (name: string, email: string, password: string) => Promise<string | null>
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
