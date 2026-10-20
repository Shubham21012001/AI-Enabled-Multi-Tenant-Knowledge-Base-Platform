import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Loader2 } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { useAuth } from '../../store/auth'
import AuthShell, { FormError } from './AuthShell'
import { passwordProblem } from './Register'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const problem = password ? passwordProblem(password) : ''

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await api.post('/auth/reset-password', { token, new_password: password })
      useAuth.getState().clear()
      toast.success('Password updated — please sign in.')
      navigate('/login', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Choose a new password"
      footer={<Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">Back to sign in</Link>}
    >
      <form onSubmit={submit} className="space-y-4">
        <FormError message={!token ? 'This reset link is missing its token.' : error} />
        <div>
          <label htmlFor="pw" className="label">New password</label>
          <input id="pw" type="password" className="input" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className={`mt-1 text-xs ${problem ? 'text-amber-600' : 'text-slate-500'}`}>
            {problem || 'At least 8 characters, with letters and numbers.'}
          </p>
        </div>
        <button className="btn-primary w-full" disabled={loading || !token || !password || !!problem}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Update password
        </button>
      </form>
    </AuthShell>
  )
}
