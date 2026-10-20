import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Loader2 } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { useAuth } from '../../store/auth'
import { Badge } from '../../components/ui'
import { passwordProblem } from '../auth/Register'
import { Section } from './Settings'

export default function ProfileTab() {
  const { user, setUser, setTokens } = useAuth()
  const [name, setName] = useState(user.full_name)
  const [pw, setPw] = useState({ current_password: '', new_password: '' })

  const saveName = useMutation({
    mutationFn: () => api.patch('/auth/me', { full_name: name }),
    onSuccess: ({ data }) => {
      setUser(data)
      toast.success('Profile updated')
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  const changePw = useMutation({
    mutationFn: () => api.post('/auth/change-password', pw),
    onSuccess: ({ data }) => {
      setTokens(data)
      setPw({ current_password: '', new_password: '' })
      toast.success('Password changed. Other sessions were signed out.')
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  const problem = pw.new_password ? passwordProblem(pw.new_password) : ''

  return (
    <div className="space-y-6">
      <Section
        title="Profile"
        description="Your personal details."
        footer={
          <button className="btn-primary" disabled={!name.trim() || name === user.full_name || saveName.isPending} onClick={() => saveName.mutate()}>
            {saveName.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Save
          </button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="name" className="label">Full name</label>
            <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
          </div>
          <div>
            <label htmlFor="email" className="label">Email</label>
            <input id="email" className="input bg-slate-50 text-slate-500" value={user.email} disabled />
          </div>
          <div>
            <span className="label">Role</span>
            <Badge tone={user.role}>{user.role === 'admin' ? 'Admin' : 'Member'}</Badge>
          </div>
        </div>
      </Section>

      <Section
        title="Password"
        description="Changing your password signs you out on all other devices."
        footer={
          <button className="btn-primary" disabled={!pw.current_password || !pw.new_password || !!problem || changePw.isPending} onClick={() => changePw.mutate()}>
            {changePw.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Change password
          </button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="cur" className="label">Current password</label>
            <input id="cur" type="password" autoComplete="current-password" className="input" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
          </div>
          <div>
            <label htmlFor="new" className="label">New password</label>
            <input id="new" type="password" autoComplete="new-password" className="input" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            {problem && <p className="mt-1 text-xs text-amber-600">{problem}</p>}
          </div>
        </div>
      </Section>
    </div>
  )
}
