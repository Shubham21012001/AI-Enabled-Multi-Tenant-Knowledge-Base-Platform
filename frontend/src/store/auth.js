import { create } from 'zustand'

const STORAGE_KEY = 'knowbot.refresh'

function readRefresh() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

/**
 * The short-lived access token (15 min) lives only in memory. The refresh
 * token is persisted so a page reload keeps the user signed in; the backend
 * rotates it on every use and revokes all sessions if an old one is replayed.
 */
export const useAuth = create((set) => ({
  accessToken: null,
  refreshToken: readRefresh(),
  user: null,

  setTokens: ({ access_token, refresh_token }) => {
    try {
      localStorage.setItem(STORAGE_KEY, refresh_token)
    } catch {
      /* storage unavailable */
    }
    set({ accessToken: access_token, refreshToken: refresh_token })
  },
  setUser: (user) => set({ user }),
  clear: () => {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* storage unavailable */
    }
    set({ accessToken: null, refreshToken: null, user: null })
  },
}))

export const isAdmin = (user) => user?.role === 'admin'
