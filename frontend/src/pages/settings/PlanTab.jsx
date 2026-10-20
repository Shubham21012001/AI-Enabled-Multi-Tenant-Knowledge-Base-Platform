import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Check, Loader2 } from 'lucide-react'
import { api, errorMessage } from '../../lib/api'
import { ProgressBar, Spinner } from '../../components/ui'
import { Section } from './Settings'

const PLAN_INFO = {
  free: { name: 'Free', price: '₹0', blurb: 'Try KnowBot with a small team.' },
  pro: { name: 'Pro', price: '₹4,999', blurb: 'For growing teams with real knowledge bases.' },
  enterprise: { name: 'Enterprise', price: 'Custom', blurb: 'Unlimited usage for the whole company.' },
}

const fmt = (v, unit) => (v === null ? `Unlimited ${unit}` : `${v.toLocaleString()} ${unit}`)

export default function PlanTab() {
  const qc = useQueryClient()
  const [pending, setPending] = useState(null)
  const { data: plans } = useQuery({ queryKey: ['plans'], queryFn: () => api.get('/organizations/plans').then((r) => r.data) })
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: () => api.get('/organizations/me/usage').then((r) => r.data) })

  const change = useMutation({
    mutationFn: (plan) => api.put('/organizations/me/plan', { plan }),
    onSuccess: ({ data }) => {
      toast.success(`Switched to ${PLAN_INFO[data.plan].name}`)
      ;['usage', 'org', 'dashboard'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }))
    },
    onError: (e) => toast.error(errorMessage(e)),
    onSettled: () => setPending(null),
  })

  if (!plans || !usage) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <div className="space-y-6">
      <Section title="Current usage" description={`Billing month ${usage.month}. Question counts reset on the 1st.`}>
        <div className="grid gap-5 sm:grid-cols-3">
          {[
            ['Questions', usage.questions],
            ['Documents', usage.documents],
            ['Members', usage.members],
          ].map(([label, item]) => (
            <div key={label}>
              <div className="mb-1.5 flex items-baseline justify-between text-sm">
                <span className="text-slate-600">{label}</span>
                <span className="tabular-nums text-slate-900">
                  {item.used.toLocaleString()}
                  <span className="text-slate-400">{item.limit === null ? ' / ∞' : ` / ${item.limit.toLocaleString()}`}</span>
                </span>
              </div>
              <ProgressBar percent={item.limit === null ? 0 : item.percent} warning={item.warning} blocked={item.blocked} />
            </div>
          ))}
        </div>
      </Section>

      <div className="grid gap-4 md:grid-cols-3">
        {Object.entries(plans).map(([id, limits]) => {
          const current = usage.plan === id
          const info = PLAN_INFO[id]
          return (
            <div key={id} className={`card relative flex flex-col p-5 ${current ? 'ring-2 ring-brand-500' : ''}`}>
              {id === 'pro' && !current && (
                <span className="absolute -top-2.5 right-4 rounded-full bg-brand-500 px-2 py-0.5 text-[11px] font-semibold text-white">Popular</span>
              )}
              <h3 className="text-base font-semibold text-slate-900">{info.name}</h3>
              <p className="mt-1 text-sm text-slate-500">{info.blurb}</p>
              <p className="mt-4 text-2xl font-semibold text-slate-900">
                {info.price}
                {id === 'pro' && <span className="text-sm font-normal text-slate-500"> /month</span>}
              </p>
              <ul className="mt-4 flex-1 space-y-2 text-sm text-slate-600">
                {[fmt(limits.members, 'members'), fmt(limits.documents, 'documents'), `${fmt(limits.questions_per_month, 'questions')} / month`].map((t) => (
                  <li key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-brand-500" /> {t}</li>
                ))}
              </ul>
              <button
                className={`mt-5 w-full ${current ? 'btn-secondary' : 'btn-primary'}`}
                disabled={current || change.isPending}
                onClick={() => {
                  setPending(id)
                  change.mutate(id)
                }}
              >
                {pending === id && <Loader2 className="h-4 w-4 animate-spin" />}
                {current ? 'Current plan' : `Switch to ${info.name}`}
              </button>
            </div>
          )
        })}
      </div>
      <p className="text-xs text-slate-400">
        Demo billing: plan changes apply instantly. A production deployment would confirm payment with a provider first.
      </p>
    </div>
  )
}
