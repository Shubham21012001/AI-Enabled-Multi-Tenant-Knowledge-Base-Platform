import { api } from './api'
import { useAuth } from '../store/auth'

/** Store tokens from login/register/accept-invite and load the user. */
export async function startSession(tokens) {
  useAuth.getState().setTokens(tokens)
  const { data } = await api.get('/auth/me')
  useAuth.getState().setUser(data)
  return data
}

export async function logout() {
  const { refreshToken, clear } = useAuth.getState()
  try {
    if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken })
  } catch {
    /* already invalid — fine */
  } finally {
    clear()
  }
}
