import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Check, Copy, Loader2, Mail, Trash2, UserPlus, X } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { useAuth } from '../../store/auth'
import { Badge, ConfirmModal, Modal, Spinner, formatDate } from '../../components/ui'
import { Section } from './Settings'

export default function MembersTab({ admin }) {
  const me = useAuth((s) => s.user)
  const qc = useQueryClient()
  const [inviteOpen, setInviteOpen] = useState(false)
  const [toRemove, setToRemove] = useState(null)

  const { data: members } = useQuery({ queryKey: ['members'], queryFn: () => api.get('/organizations/me/members').then((r) => r.data) })
  const { data: invites } = useQuery({
    queryKey: ['invitations'],
    queryFn: () => api.get('/organizations/me/invitations').then((r) => r.data),
    enabled: admin,
  })
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: () => api.get('/organizations/me/usage').then((r) => r.data) })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['members'] })
    qc.invalidateQueries({ queryKey: ['invitations'] })
    qc.invalidateQueries({ queryKey: ['usage'] })
    qc.invalidateQueries({ queryKey: ['org'] })
  }

  const changeRole = useMutation({
    mutationFn: ({ id, role }) => api.patch(`/organizations/me/members/${id}`, { role }),
    onSuccess: () => {
      toast.success('Role updated')
      refresh()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const remove = useMutation({
    mutationFn: (id) => api.delete(`/organizations/me/members/${id}`),
    onSuccess: () => {
      toast.success('Member removed')
      setToRemove(null)
      refresh()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const revokeInvite = useMutation({
    mutationFn: (id) => api.delete(`/organizations/me/invitations/${id}`),
    onSuccess: () => {
      toast.success('Invitation revoked')
      refresh()
    },
  })

  const seats = usage?.members
  return (
    <div className="space-y-6">
      <Section
        title="Members"
        description={
          seats &&
          (seats.limit === null ? `${seats.used} members · unlimited seats` : `${seats.used} of ${seats.limit} seats used (pending invitations reserve a seat)`)
        }
      >
        {admin && (
          <div className="-mt-1 mb-4 flex justify-end">
            <button className="btn-primary" onClick={() => setInviteOpen(true)}>
              <UserPlus className="h-4 w-4" /> Invite member
            </button>
          </div>
        )}
        {!members ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <ul className="-mx-5 divide-y divide-slate-100">
            {members.map((m) => (
              <li key={m.id} className="flex flex-col gap-3 px-5 py-3 sm:flex-row sm:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
                    {m.full_name.slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {m.full_name} {m.id === me.id && <span className="font-normal text-slate-400">(you)</span>}
                    </p>
                    <p className="truncate text-xs text-slate-500">{m.email} · joined {formatDate(m.created_at)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 pl-12 sm:pl-0">
                  {admin && m.id !== me.id ? (
                    <select
                      className="input w-auto min-w-[120px] py-0"
                      value={m.role}
                      onChange={(e) => changeRole.mutate({ id: m.id, role: e.target.value })}
                      aria-label={`Role for ${m.full_name}`}
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                  ) : (
                    <Badge tone={m.role}>{m.role === 'admin' ? 'Admin' : 'Member'}</Badge>
                  )}
                  {admin && m.id !== me.id && (
                    <button onClick={() => setToRemove(m)} className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label={`Remove ${m.full_name}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {admin && invites?.length > 0 && (
        <Section title="Pending invitations">
          <ul className="-mx-5 divide-y divide-slate-100">
            {invites.map((inv) => (
              <li key={inv.id} className="flex items-center gap-3 px-5 py-3">
                <Mail className="h-4 w-4 shrink-0 text-slate-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-slate-900">{inv.email}</p>
                  <p className="text-xs text-slate-500">
                    {inv.role} · expires {formatDate(inv.expires_at)}
                  </p>
                </div>
                <button onClick={() => revokeInvite.mutate(inv.id)} className="btn-ghost px-3 text-xs text-red-600 hover:bg-red-50">
                  <X className="h-4 w-4" /> Revoke
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <InviteModal open={inviteOpen} onClose={() => setInviteOpen(false)} onDone={refresh} />
      <ConfirmModal
        open={!!toRemove}
        onClose={() => setToRemove(null)}
        onConfirm={() => remove.mutate(toRemove.id)}
        loading={remove.isPending}
        title="Remove member?"
        confirmLabel="Remove"
        message={toRemove && `${toRemove.full_name} will lose access immediately. Their past questions stay in your analytics.`}
      />
    </div>
  )
}

function InviteModal({ open, onClose, onDone }) {
  const [form, setForm] = useState({ email: '', role: 'member' })
  const [link, setLink] = useState('')
  const [copied, setCopied] = useState(false)

  const invite = useMutation({
    mutationFn: () => api.post('/organizations/me/invitations', form),
    onSuccess: ({ data }) => {
      setLink(data.invite_url)
      onDone()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  function close() {
    setForm({ email: '', role: 'member' })
    setLink('')
    setCopied(false)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={link ? 'Invitation sent' : 'Invite a teammate'}
      footer={
        link ? (
          <button className="btn-primary" onClick={close}>Done</button>
        ) : (
          <>
            <button className="btn-secondary" onClick={close}>Cancel</button>
            <button className="btn-primary" disabled={!form.email || invite.isPending} onClick={() => invite.mutate()}>
              {invite.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Send invite
            </button>
          </>
        )
      }
    >
      {link ? (
        <div>
          <p className="text-sm text-slate-600">
            We emailed <strong>{form.email}</strong>. You can also share this one-time link (valid for 7 days):
          </p>
          <div className="mt-3 flex gap-2">
            <input readOnly value={link} className="input font-mono text-xs" onFocus={(e) => e.target.select()} aria-label="Invitation link" />
            <button
              className="btn-secondary shrink-0 px-3"
              onClick={() => {
                navigator.clipboard?.writeText(link)
                setCopied(true)
              }}
              aria-label="Copy link"
            >
              {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label htmlFor="inv-email" className="label">Email address</label>
            <input id="inv-email" type="email" className="input" placeholder="colleague@company.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <span className="label">Role</span>
            <div className="grid grid-cols-2 gap-2">
              {[
                ['member', 'Member', 'Ask questions'],
                ['admin', 'Admin', 'Manage docs & team'],
              ].map(([value, label, hint]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setForm({ ...form, role: value })}
                  className={`min-h-[44px] rounded-lg border px-3 py-2 text-left transition ${form.role === value ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500' : 'border-slate-200 hover:bg-slate-50'}`}
                  aria-pressed={form.role === value}
                >
                  <span className="block text-sm font-medium text-slate-900">{label}</span>
                  <span className="block text-xs text-slate-500">{hint}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}
