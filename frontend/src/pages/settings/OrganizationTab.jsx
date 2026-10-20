import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Building2, Loader2 } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { Spinner, formatDate } from '../../components/ui'
import { Section } from './Settings'

export default function OrganizationTab({ admin }) {
  const qc = useQueryClient()
  const { data: org } = useQuery({ queryKey: ['org'], queryFn: () => api.get('/organizations/me').then((r) => r.data) })
  const [form, setForm] = useState({ name: '', logo_url: '' })
  useEffect(() => {
    if (org) setForm({ name: org.name, logo_url: org.logo_url || '' })
  }, [org])

  const save = useMutation({
    mutationFn: () => api.patch('/organizations/me', { name: form.name, logo_url: form.logo_url || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['org'] })
      toast.success('Organization updated')
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  if (!org) return <div className="flex justify-center py-12"><Spinner /></div>
  const dirty = form.name !== org.name || (form.logo_url || '') !== (org.logo_url || '')

  return (
    <Section
      title="Organization"
      description={admin ? 'Your workspace details, visible to all members.' : 'Only admins can edit these details.'}
      footer={
        admin && (
          <button className="btn-primary" disabled={!dirty || form.name.trim().length < 2 || save.isPending} onClick={() => save.mutate()}>
            {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Save changes
          </button>
        )
      }
    >
      <div className="flex flex-col gap-6 sm:flex-row">
        <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
          {org.logo_url ? (
            <img src={org.logo_url} alt={`${org.name} logo`} className="h-full w-full object-contain" referrerPolicy="no-referrer" />
          ) : (
            <Building2 className="h-8 w-8 text-slate-300" />
          )}
        </div>
        <div className="grid flex-1 gap-4">
          <div>
            <label htmlFor="org-name" className="label">Organization name</label>
            <input id="org-name" className="input" disabled={!admin} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={200} />
          </div>
          <div>
            <label htmlFor="logo" className="label">Logo URL</label>
            <input id="logo" className="input" disabled={!admin} placeholder="https://…" value={form.logo_url} onChange={(e) => setForm({ ...form, logo_url: e.target.value })} />
          </div>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div><dt className="text-slate-500">Plan</dt><dd className="font-medium capitalize text-slate-900">{org.plan}</dd></div>
            <div><dt className="text-slate-500">Members</dt><dd className="font-medium text-slate-900">{org.members_count}</dd></div>
            <div><dt className="text-slate-500">Created</dt><dd className="font-medium text-slate-900">{formatDate(org.created_at)}</dd></div>
          </dl>
        </div>
      </div>
    </Section>
  )
}
