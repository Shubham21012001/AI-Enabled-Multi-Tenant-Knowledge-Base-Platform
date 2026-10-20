import axios from 'axios'
import { useAuth } from '../store/auth'

export const API_BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({ baseURL: API_BASE })

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// One refresh at a time: concurrent 401s wait for the same refresh promise.
let refreshing = null

export async function refreshTokens() {
  if (!refreshing) {
    const { setTokens, clear } = useAuth.getState()
    // Re-read storage: another tab may already have rotated the token.
    let refreshToken = useAuth.getState().refreshToken
    try {
      refreshToken = localStorage.getItem('knowbot.refresh') || refreshToken
    } catch {
      /* storage unavailable */
    }
    refreshing = (async () => {
      if (!refreshToken) throw new Error('No refresh token')
      try {
        const { data } = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refreshToken })
        setTokens(data)
        return data.access_token
      } catch (err) {
        // Only an invalid/expired/revoked token ends the session. A 429 or a
        // network blip must not log the user out.
        if (err.response?.status === 401) clear()
        throw err
      }
    })().finally(() => {
      refreshing = null
    })
  }
  return refreshing
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const isAuthCall = original?.url?.startsWith('/auth/login') || original?.url?.startsWith('/auth/refresh')
    if (error.response?.status === 401 && !original._retried && !isAuthCall && useAuth.getState().refreshToken) {
      original._retried = true
      const token = await refreshTokens()
      original.headers.Authorization = `Bearer ${token}`
      return api(original)
    }
    return Promise.reject(error)
  },
)

export function errorMessage(err, fallback = 'Something went wrong') {
  return err?.response?.data?.detail || err?.message || fallback
}
