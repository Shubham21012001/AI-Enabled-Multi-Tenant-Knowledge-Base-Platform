import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { AlertTriangle, Check, Copy, KeyRound, Loader2, Plus } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { Badge, ConfirmModal, EmptyState, Modal, Spinner, formatDate, timeAgo } from '../../components/ui'
import { Section } from './Settings'

export default function ApiKeysTab() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [toRevoke, setToRevoke] = useState(null)
  const { data: keys } = useQuery({ queryKey: ['api-keys'], queryFn: () => api.get('/api-keys').then((r) => r.data) })

  const revoke = useMutation({
    mutationFn: (id) => api.delete(`/api-keys/${id}`),
    onSuccess: () => {
      toast.success('API key revoked')
      setToRevoke(null)
      qc.invalidateQueries({ queryKey: ['api-keys'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  return (
    <div className="space-y-6">
      <Section title="API keys" description="Let other tools (Slack bots, intranet widgets) ask KnowBot questions on behalf of your organization.">
        <div className="-mt-1 mb-4 flex justify-end">
          <button className="btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Create key
          </button>
        </div>
        {!keys ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : keys.length === 0 ? (
          <EmptyState icon={KeyRound} title="No API keys" description="Create a key to call POST /chat/ask with the X-API-Key header." />
        ) : (
          <ul className="-mx-5 divide-y divide-slate-100">
            {keys.map((k) => (
              <li key={k.id} className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-medium text-slate-900">{k.name}</p>
                    {k.revoked_at ? <Badge tone="failed">Revoked</Badge> : <Badge tone="ready">Active</Badge>}
                  </div>
                  <p className="mt-0.5 font-mono text-xs text-slate-500">{k.prefix}••••••••</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    Created {formatDate(k.created_at)} · {k.usage_count} request{k.usage_count === 1 ? '' : 's'}
                    {k.last_used_at && ` · last used ${timeAgo(k.last_used_at)}`}
                  </p>
                </div>
                {!k.revoked_at && (
                  <button className="btn-secondary self-start text-red-600 hover:bg-red-50 sm:self-auto" onClick={() => setToRevoke(k)}>
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Usage example">
        <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
{`curl -N -X POST https://<your-knowbot-host>/api/chat/ask \\
  -H "X-API-Key: kb_live_..." \\
  -H "Content-Type: application/json" \\
  -d '{"question": "How many days of annual leave do we get?"}'`}
        </pre>
      </Section>

      <CreateKeyModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={() => qc.invalidateQueries({ queryKey: ['api-keys'] })} />
      <ConfirmModal
        open={!!toRevoke}
        onClose={() => setToRevoke(null)}
        onConfirm={() => revoke.mutate(toRevoke.id)}
        loading={revoke.isPending}
        title="Revoke API key?"
        confirmLabel="Revoke"
        message={toRevoke && `Anything using “${toRevoke.name}” will stop working immediately. This can't be undone.`}
      />
    </div>
  )
}

function CreateKeyModal({ open, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [raw, setRaw] = useState('')
  const [copied, setCopied] = useState(false)

  const create = useMutation({
    mutationFn: () => api.post('/api-keys', { name }),
    onSuccess: ({ data }) => {
      setRaw(data.key)
      onCreated()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  function close() {
    setName('')
    setRaw('')
    setCopied(false)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title={raw ? 'Save your API key' : 'Create API key'}
      footer={
        raw ? (
          <button className="btn-primary" onClick={close}>I’ve saved it</button>
        ) : (
          <>
            <button className="btn-secondary" onClick={close}>Cancel</button>
            <button className="btn-primary" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Create
            </button>
          </>
        )
      }
    >
      {raw ? (
        <div>
          <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            This is the only time the full key is shown. KnowBot stores only a hash of it.
          </div>
          <div className="mt-3 flex gap-2">
            <input readOnly value={raw} className="input font-mono text-xs" onFocus={(e) => e.target.select()} aria-label="API key" />
            <button
              className="btn-secondary shrink-0 px-3"
              onClick={() => {
                navigator.clipboard?.writeText(raw)
                setCopied(true)
              }}
              aria-label="Copy key"
            >
              {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
        </div>
      ) : (
        <div>
          <label htmlFor="key-name" className="label">Key name</label>
          <input id="key-name" className="input" placeholder="e.g. Slack bot" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
      )}
    </Modal>
  )
}
