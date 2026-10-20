import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { startSession } from '../../lib/session'
import AuthShell, { FormError } from './AuthShell'

export function passwordProblem(pw) {
  if (pw.length < 8) return 'At least 8 characters'
  if (!/[a-zA-Z]/.test(pw) || !/\d/.test(pw)) return 'Use letters and numbers'
  return ''
}

export default function Register() {
  const [form, setForm] = useState({ full_name: '', organization_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const pwProblem = form.password ? passwordProblem(form.password) : ''

  async function submit(e) {
    e.preventDefault()
    if (passwordProblem(form.password)) return setError('Please choose a stronger password.')
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/register', form)
      await startSession(data)
      navigate('/documents', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Could not create your workspace'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Start free — 5 documents and 100 questions a month."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">Sign in</Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <div>
          <label htmlFor="full_name" className="label">Your name</label>
          <input id="full_name" className="input" autoComplete="name" required value={form.full_name} onChange={set('full_name')} />
        </div>
        <div>
          <label htmlFor="org" className="label">Company name</label>
          <input id="org" className="input" autoComplete="organization" required value={form.organization_name} onChange={set('organization_name')} />
        </div>
        <div>
          <label htmlFor="email" className="label">Work email</label>
          <input id="email" type="email" className="input" autoComplete="email" required placeholder="you@company.com" value={form.email} onChange={set('email')} />
        </div>
        <div>
          <label htmlFor="password" className="label">Password</label>
          <input id="password" type="password" className="input" autoComplete="new-password" required value={form.password} onChange={set('password')} />
          <p className={`mt-1 text-xs ${pwProblem ? 'text-amber-600' : 'text-slate-500'}`}>
            {pwProblem || 'At least 8 characters, with letters and numbers.'}
          </p>
        </div>
        <button
          type="submit"
          className="btn-primary w-full"
          disabled={loading || !form.full_name || form.organization_name.length < 2 || !form.email || !!pwProblem || !form.password}
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Create workspace
        </button>
      </form>
    </AuthShell>
  )
}
