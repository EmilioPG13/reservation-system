import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setUnauthorizedHandler, tokenStore } from '../api/client'
import { errorMessage } from '../lib/messages'
import { AuthContext, type User } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => tokenStore.get() !== null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const endSession = useCallback(() => {
    tokenStore.clear()
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  // A 401 anywhere (the token lasts 30 minutes) sends the user back to the login.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      endSession()
      navigate('/entrar', { replace: true, state: { expired: true } })
    })
  }, [endSession, navigate])

  useEffect(() => {
    if (!tokenStore.get()) return
    let cancelled = false
    api.GET('/auth/me').then(({ data }) => {
      if (cancelled) return
      if (data) setUser(data)
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { data, error } = await api.POST('/auth/login', {
      // OAuth2 password form: the email travels in `username`.
      body: { username: email, password, scope: '' },
      bodySerializer: (body) => new URLSearchParams({ username: body.username, password: body.password }),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    if (!data) return errorMessage(error)
    tokenStore.set(data.access_token)
    const me = await api.GET('/auth/me')
    if (!me.data) return errorMessage(me.error)
    setUser(me.data)
    return null
  }, [])

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      const { error } = await api.POST('/auth/register', { body: { name, email, password } })
      if (error) return errorMessage(error)
      return login(email, password)
    },
    [login],
  )

  const logout = useCallback(() => {
    endSession()
    navigate('/entrar', { replace: true })
  }, [endSession, navigate])

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
