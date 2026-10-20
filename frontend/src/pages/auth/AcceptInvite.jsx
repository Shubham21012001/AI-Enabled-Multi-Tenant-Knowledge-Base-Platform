import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { startSession } from '../../lib/session'
import { useAuth } from '../../store/auth'
import { Spinner } from '../../components/ui'
import AuthShell, { FormError } from './AuthShell'
import { passwordProblem } from './Register'

export default function AcceptInvite() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const info = useQuery({
    queryKey: ['invite', token],
    queryFn: () => api.get(`/auth/invitations/${encodeURIComponent(token)}`).then((r) => r.data),
    enabled: !!token,
    retry: false,
  })

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      useAuth.getState().clear() // an invite always starts a fresh session
      const { data } = await api.post('/auth/accept-invite', { ...form, token })
      await startSession(data)
      navigate('/chat', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!token || info.isError) {
    return (
      <AuthShell title="Invitation not valid" subtitle="This invitation link is invalid, already used, or expired.">
        <Link to="/login" className="btn-primary w-full">Go to sign in</Link>
      </AuthShell>
    )
  }
  if (info.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="h-8 w-8" />
      </div>
    )
  }

  const pwProblem = form.password ? passwordProblem(form.password) : ''
  return (
    <AuthShell
      title={`Join ${info.data.organization_name}`}
      subtitle={`You've been invited as ${info.data.role === 'admin' ? 'an admin' : 'a member'} (${info.data.email}).`}
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <div>
          <label htmlFor="name" className="label">Your name</label>
          <input id="name" className="input" autoComplete="name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </div>
        <div>
          <label htmlFor="pw" className="label">Choose a password</label>
          <input id="pw" type="password" className="input" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <p className={`mt-1 text-xs ${pwProblem ? 'text-amber-600' : 'text-slate-500'}`}>
            {pwProblem || 'At least 8 characters, with letters and numbers.'}
          </p>
        </div>
        <button type="submit" className="btn-primary w-full" disabled={loading || !form.full_name || !form.password || !!pwProblem}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Join workspace
        </button>
      </form>
    </AuthShell>
  )
}
