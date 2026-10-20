import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api, refreshTokens } from './lib/api'
import { isAdmin, useAuth } from './store/auth'
import AppLayout from './components/AppLayout'
import { FullPageSpinner } from './components/ui'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import AcceptInvite from './pages/auth/AcceptInvite'
import ForgotPassword from './pages/auth/ForgotPassword'
import ResetPassword from './pages/auth/ResetPassword'
import Chat from './pages/Chat'
import Documents from './pages/Documents'
import Dashboard from './pages/Dashboard'
import Settings from './pages/settings/Settings'
import NotFound from './pages/NotFound'

/** On load, turn a stored refresh token into a session. */
function useBootstrapSession() {
  const { refreshToken, accessToken, setUser } = useAuth()
  const [ready, setReady] = useState(!refreshToken || !!accessToken)

  useEffect(() => {
    let cancelled = false
    if (refreshToken && !accessToken) {
      refreshTokens()
        .then(() => api.get('/auth/me'))
        .then(({ data }) => !cancelled && setUser(data))
        .catch(() => {})
        .finally(() => !cancelled && setReady(true))
    }
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return ready
}

function RequireAuth({ children }) {
  const { accessToken, user } = useAuth()
  const location = useLocation()
  if (!accessToken || !user) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}

function RequireAdmin({ children }) {
  const user = useAuth((s) => s.user)
  return isAdmin(user) ? children : <Navigate to="/chat" replace />
}

function GuestOnly({ children }) {
  const { accessToken, user } = useAuth()
  return accessToken && user ? <Navigate to="/chat" replace /> : children
}

export default function App() {
  const ready = useBootstrapSession()
  const accessToken = useAuth((s) => s.accessToken)
  const queryClient = useQueryClient()

  // Drop all cached server data when the session ends (e.g. logout, revoked token).
  useEffect(() => {
    if (!accessToken) queryClient.clear()
  }, [accessToken, queryClient])

  if (!ready) return <FullPageSpinner />

  return (
    <Routes>
      <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
      <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />
      <Route path="/accept-invite" element={<AcceptInvite />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/dashboard" element={<RequireAdmin><Dashboard /></RequireAdmin>} />
        <Route path="/settings" element={<Navigate to="/settings/profile" replace />} />
        <Route path="/settings/:tab" element={<Settings />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
