import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, FileText, HelpCircle, Lightbulb, MessageSquare, Table2, BarChart3, ThumbsDown, ThumbsUp, Users, Zap } from 'lucide-react'
import { api } from '../lib/api'
import DailyChart from '../components/DailyChart'
import { FileIcon, PageHeader, ProgressBar, Spinner, timeAgo } from '../components/ui'

const RANGES = [7, 30, 90]

export default function Dashboard() {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', days],
    queryFn: () => api.get('/dashboard', { params: { days } }).then((r) => r.data),
    refetchInterval: 60_000,
  })

  if (isLoading || !data) {
    return <div className="flex justify-center py-24"><Spinner className="h-6 w-6" /></div>
  }

  const { usage, questions, feedback } = data
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      <PageHeader
        title="Dashboard"
        description={`How ${data.organization.name} is using KnowBot.`}
        actions={
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1" role="group" aria-label="Time range">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setDays(r)}
                aria-pressed={days === r}
                className={`min-h-[36px] rounded-md px-3 text-sm font-medium transition ${days === r ? 'bg-brand-500 text-white' : 'text-slate-600 hover:bg-slate-50'}`}
              >
                {r}d
              </button>
            ))}
          </div>
        }
      />

      {/* Usage vs plan */}
      <div className="grid gap-4 md:grid-cols-3">
        <UsageCard icon={MessageSquare} label="Questions this month" item={usage.questions} plan={usage.plan} />
        <UsageCard icon={FileText} label="Documents" item={usage.documents} plan={usage.plan} />
        <UsageCard icon={Users} label="Members" item={usage.members} plan={usage.plan} />
      </div>

      {/* Secondary stats */}
      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={CheckCircle2} label="Answer rate" value={questions.answer_rate === null ? '—' : `${questions.answer_rate}%`} hint={`${questions.answered} of ${questions.total} answered`} />
        <Stat icon={HelpCircle} label="Unanswered" value={questions.unanswered} hint="Knowledge gaps" />
        <Stat icon={Zap} label="Instant (cached)" value={questions.cache_hits} hint="Served from cache" />
        <Stat
          icon={ThumbsUp}
          label="Feedback"
          value={
            <span className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1"><ThumbsUp className="h-4 w-4 text-slate-400" />{feedback.thumbs_up}</span>
              <span className="inline-flex items-center gap-1"><ThumbsDown className="h-4 w-4 text-slate-400" />{feedback.thumbs_down}</span>
            </span>
          }
          hint="Helpful vs not helpful"
        />
      </div>

      <DailyCard data={data.daily_questions} days={days} total={questions.total} />

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Most asked questions" icon={MessageSquare}>
          {data.most_asked.length ? (
            <ol className="divide-y divide-slate-100">
              {data.most_asked.map((q, i) => (
                <li key={q.question} className="flex items-center gap-3 py-2.5">
                  <span className="w-5 shrink-0 text-xs font-semibold tabular-nums text-slate-400">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-700" title={q.question}>{q.question}</span>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium tabular-nums text-slate-600">{q.count}×</span>
                </li>
              ))}
            </ol>
          ) : (
            <Empty text="No questions asked in this period yet." />
          )}
        </Card>

        <Card
          title="Knowledge gaps"
          icon={Lightbulb}
          subtitle="Questions KnowBot couldn't answer or that got a thumbs down. Add documents that cover them."
        >
          {data.knowledge_gaps.length ? (
            <ul className="divide-y divide-slate-100">
              {data.knowledge_gaps.map((g) => (
                <li key={g.question} className="flex items-start gap-3 py-2.5">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-700">{g.question}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {g.unanswered_count > 0 && `Not found ${g.unanswered_count}×`}
                      {g.unanswered_count > 0 && g.thumbs_down_count > 0 && ' · '}
                      {g.thumbs_down_count > 0 && `${g.thumbs_down_count} thumbs down`}
                      {' · '}last asked {timeAgo(g.last_asked)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty text="No gaps found — every question in this period was answered." />
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card title="Most cited documents" icon={FileText} subtitle="All-time number of answers that cited each document.">
          {data.most_cited_documents.length ? (
            <ul className="space-y-3">
              {data.most_cited_documents.map((d) => {
                const max = data.most_cited_documents[0].question_count
                return (
                  <li key={d.document_id} className="flex items-center gap-3">
                    <FileIcon type={d.file_type} className="h-8 w-8" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="truncate text-sm text-slate-700">{d.document_name}</span>
                        <span className="shrink-0 text-xs font-medium tabular-nums text-slate-600">{d.question_count}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-slate-100">
                        <motion.div
                          className="h-full rounded-full bg-brand-500"
                          initial={{ width: 0 }}
                          animate={{ width: `${(d.question_count / max) * 100}%` }}
                          transition={{ duration: 0.6 }}
                        />
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : (
            <Empty text={<>No answers have cited documents yet. <Link to="/chat" className="font-medium text-brand-600">Ask a question</Link>.</>} />
          )}
        </Card>
      </div>
    </div>
  )
}

function UsageCard({ icon: Icon, label, item, plan }) {
  const unlimited = item.limit === null
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <Icon className="h-4 w-4 text-slate-400" />
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="text-3xl font-semibold tabular-nums tracking-tight text-slate-900">{item.used.toLocaleString()}</span>
        <span className="text-sm text-slate-500">{unlimited ? 'unlimited' : `/ ${item.limit.toLocaleString()}`}</span>
      </div>
      {!unlimited && (
        <>
          <ProgressBar percent={item.percent} warning={item.warning} blocked={item.blocked} className="mt-3" />
          <p className={`mt-2 flex items-center gap-1 text-xs ${item.blocked ? 'text-red-600' : item.warning ? 'text-amber-700' : 'text-slate-500'}`}>
            {(item.warning || item.blocked) && <AlertTriangle className="h-3.5 w-3.5" />}
            {item.blocked ? (
              <>Limit reached · <Link to="/settings/plan" className="font-medium underline">Upgrade</Link></>
            ) : item.warning ? (
              <>{item.percent}% used · <Link to="/settings/plan" className="font-medium underline">Upgrade</Link></>
            ) : (
              `${item.remaining.toLocaleString()} remaining on ${plan}`
            )}
          </p>
        </>
      )}
    </div>
  )
}

function Stat({ icon: Icon, label, value, hint }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
        <Icon className="h-4 w-4 text-slate-400" /> {label}
      </div>
      <div className="mt-1.5 text-xl font-semibold tabular-nums text-slate-900">{value}</div>
      <p className="mt-0.5 text-xs text-slate-400">{hint}</p>
    </div>
  )
}

function DailyCard({ data, days, total }) {
  const [table, setTable] = useState(false)
  return (
    <div className="card mt-4 p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Questions per day</h2>
          <p className="text-xs text-slate-500">{total.toLocaleString()} in the last {days} days</p>
        </div>
        <button onClick={() => setTable((t) => !t)} className="btn-ghost px-3 text-xs" aria-pressed={table}>
          {table ? <BarChart3 className="h-4 w-4" /> : <Table2 className="h-4 w-4" />}
          {table ? 'Chart' : 'Table'}
        </button>
      </div>
      {table ? (
        <div className="max-h-64 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white text-left text-xs text-slate-500">
              <tr><th className="py-1.5 font-medium">Date</th><th className="py-1.5 text-right font-medium">Questions</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[...data].reverse().map((d) => (
                <tr key={d.date}>
                  <td className="py-1.5 text-slate-700">{new Date(d.date + 'T00:00:00').toLocaleDateString()}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-700">{d.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <DailyChart data={data} />
      )}
    </div>
  )
}

function Card({ title, subtitle, icon: Icon, children }) {
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-4 w-4 text-brand-500" />
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      </div>
      {subtitle && <p className="-mt-2 mb-3 text-xs text-slate-500">{subtitle}</p>}
      {children}
    </div>
  )
}

function Empty({ text }) {
  return <p className="py-6 text-center text-sm text-slate-400">{text}</p>
}

