import createClient, { type Middleware } from 'openapi-fetch'
import type { paths } from './schema'

const TOKEN_KEY = 'access_token'

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

// Called when the API says the session is gone (the token lasts 30 minutes, no refresh).
let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

const auth: Middleware = {
  onRequest({ request }) {
    const token = tokenStore.get()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    return request
  },
  onResponse({ request, response }) {
    // A 401 from /auth/login only means a wrong password; it must not end a session.
    if (response.status === 401 && !new URL(request.url).pathname.endsWith('/auth/login')) {
      tokenStore.clear()
      onUnauthorized()
    }
    return response
  },
}

export const api = createClient<paths>({ baseUrl: '/api' })
api.use(auth)
