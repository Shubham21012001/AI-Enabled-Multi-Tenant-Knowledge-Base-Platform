import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  AlertTriangle,
  ArrowUp,
  Bot,
  FileText,
  History,
  Plus,
  Search,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  Upload,
  X,
  Zap,
} from 'lucide-react'
import { api } from '../lib/api'
import { streamQuestion } from '../lib/stream'
import { isAdmin, useAuth } from '../store/auth'
import AnswerText from '../components/AnswerText'
import { timeAgo } from '../components/ui'

const EXAMPLES = [
  'How many days of annual leave do employees get?',
  'What is the process for submitting expenses?',
  'Summarise our remote work policy.',
  'Who should I contact for IT support?',
]

let nextId = 1

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [usageWarning, setUsageWarning] = useState(null)
  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const stickToBottom = useRef(true)
  const qc = useQueryClient()
  const user = useAuth((s) => s.user)

  const { data: docs } = useQuery({ queryKey: ['documents'], queryFn: () => api.get('/documents/').then((r) => r.data) })
  const readyDocs = docs ? docs.filter((d) => d.status === 'ready').length : null

  // Keep the newest tokens in view unless the user scrolled up to read.
  useEffect(() => {
    const el = scrollRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [messages])

  useEffect(() => () => abortRef.current?.abort(), [])

  const patch = (id, fn) => setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)))

  const ask = useCallback(
    async (question) => {
      const q = question.trim()
      if (!q || streaming) return
      setInput('')
      stickToBottom.current = true
      const userMsg = { id: nextId++, role: 'user', content: q }
      const botId = nextId++
      setMessages((ms) => [...ms, userMsg, { id: botId, role: 'assistant', content: '', streaming: true, sources: [] }])
      setStreaming(true)
      const controller = new AbortController()
      abortRef.current = controller
      try {
        await streamQuestion(q, {
          signal: controller.signal,
          onEvent: (ev) => {
            if (ev.type === 'token') patch(botId, (m) => ({ content: m.content + ev.content }))
            else if (ev.type === 'meta') patch(botId, () => ({ cached: ev.cached }))
            else if (ev.type === 'sources') patch(botId, () => ({ sources: ev.sources }))
            else if (ev.type === 'error') patch(botId, () => ({ error: ev.message }))
            else if (ev.type === 'done') {
              patch(botId, () => ({ conversationId: ev.conversation_id }))
              if (ev.usage?.warning) setUsageWarning(ev.usage)
            }
          },
        })
      } catch (err) {
        if (err.name !== 'AbortError') {
          patch(botId, () => ({ error: err.message }))
          if (err.status === 402) setUsageWarning({ blocked: true })
          if (err.status === 429) toast.error('You are asking too quickly. Please wait a moment.')
        }
      } finally {
        patch(botId, (m) => ({ streaming: false, content: m.content.trim() }))
        setStreaming(false)
        abortRef.current = null
        qc.invalidateQueries({ queryKey: ['conversations'] })
      }
    },
    [streaming, qc],
  )

  function loadConversation(c) {
    abortRef.current?.abort()
    setMessages([
      { id: nextId++, role: 'user', content: c.question },
      {
        id: nextId++,
        role: 'assistant',
        content: c.answer,
        sources: c.sources,
        conversationId: c.id,
        feedback: c.feedback,
        cached: c.from_cache,
      },
    ])
    setHistoryOpen(false)
  }

  function newChat() {
    abortRef.current?.abort()
    setMessages([])
    setHistoryOpen(false)
  }

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Toolbar */}
        <div className="flex items-center justify-between gap-2 border-b border-slate-100 bg-white/80 px-3 py-1.5 backdrop-blur sm:px-6">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className={`h-2 w-2 rounded-full ${readyDocs ? 'bg-emerald-500' : 'bg-slate-300'}`} />
            {readyDocs === null ? 'Loading documents…' : `${readyDocs} document${readyDocs === 1 ? '' : 's'} searchable`}
          </div>
          <div className="flex gap-1">
            <button className="btn-ghost px-3" onClick={newChat} disabled={!messages.length}>
              <Plus className="h-4 w-4" /> <span className="hidden sm:inline">New chat</span>
            </button>
            <button className="btn-ghost px-3 xl:hidden" onClick={() => setHistoryOpen(true)}>
              <History className="h-4 w-4" /> <span className="hidden sm:inline">History</span>
            </button>
          </div>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="min-h-0 flex-1 overflow-y-auto"
          onScroll={(e) => {
            const el = e.currentTarget
            stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
          }}
        >
          <div className="mx-auto w-full max-w-[800px] px-4 py-6 sm:px-6">
            {messages.length === 0 ? (
              <EmptyChat readyDocs={readyDocs} admin={isAdmin(user)} onPick={ask} name={user?.full_name?.split(' ')[0]} />
            ) : (
              <div className="space-y-6">
                <AnimatePresence initial={false}>
                  {messages.map((m) =>
                    m.role === 'user' ? <UserBubble key={m.id} text={m.content} /> : <BotMessage key={m.id} msg={m} />,
                  )}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-slate-200 bg-white px-3 pb-[max(env(safe-area-inset-bottom),12px)] pt-3 sm:px-6">
          <div className="mx-auto max-w-[800px]">
            {usageWarning && <UsageBanner usage={usageWarning} onClose={() => setUsageWarning(null)} />}
            <Composer value={input} onChange={setInput} onSend={() => ask(input)} onStop={() => abortRef.current?.abort()} streaming={streaming} />
            <p className="mt-2 text-center text-[11px] text-slate-400">
              Answers come only from your company’s documents. Check the sources for important decisions.
            </p>
          </div>
        </div>
      </div>

      <HistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} onSelect={loadConversation} />
    </div>
  )
}

function EmptyChat({ readyDocs, admin, onPick, name }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center pt-6 text-center sm:pt-14">
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-pop">
        <Sparkles className="h-7 w-7 text-white" />
      </div>
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
        {name ? `Hi ${name}, what do you need to know?` : 'What do you need to know?'}
      </h1>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        Ask anything about your company’s policies, processes and manuals. Every answer links to the documents it came from.
      </p>

      {readyDocs === null ? null : readyDocs === 0 ? (
        <div className="mt-8 w-full max-w-md rounded-lg border border-dashed border-slate-300 bg-white p-6">
          <FileText className="mx-auto h-6 w-6 text-slate-400" />
          <p className="mt-2 text-sm font-medium text-slate-700">No documents are ready yet</p>
          <p className="mt-1 text-sm text-slate-500">
            {admin ? 'Upload a PDF, DOCX or TXT file to start asking questions.' : 'Ask your admin to upload company documents.'}
          </p>
          {admin && (
            <Link to="/documents" className="btn-primary mt-4">
              <Upload className="h-4 w-4" /> Upload documents
            </Link>
          )}
        </div>
      ) : (
        <div className="mt-8 grid w-full gap-2 sm:grid-cols-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              onClick={() => onPick(q)}
              className="group min-h-[44px] rounded-lg border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-card transition hover:border-brand-300 hover:bg-brand-50/40"
            >
              <span className="line-clamp-2">{q}</span>
            </button>
          ))}
        </div>
      )}
    </motion.div>
  )
}

function UserBubble({ text }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand-500 px-4 py-2.5 text-[15px] text-white shadow-sm">
        {text}
      </div>
    </motion.div>
  )
}

function BotMessage({ msg }) {
  const waiting = msg.streaming && !msg.content
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sidebar">
        <Bot className="h-4 w-4 text-white" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-medium text-slate-700">KnowBot</span>
          {msg.cached && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
              <Zap className="h-3 w-3" /> Instant answer
            </span>
          )}
        </div>
        {waiting ? (
          <div className="flex items-center gap-2 py-1.5 text-sm text-slate-500">
            <Search className="h-4 w-4 animate-pulse text-brand-500" /> Searching your documents…
          </div>
        ) : (
          <AnswerText text={msg.content} streaming={msg.streaming} />
        )}
        {msg.error && (
          <div className="mt-2 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {msg.error}
          </div>
        )}
        {!msg.streaming && msg.sources?.length > 0 && <Sources sources={msg.sources} />}
        {!msg.streaming && msg.conversationId && <Feedback conversationId={msg.conversationId} initial={msg.feedback} />}
      </div>
    </motion.div>
  )
}

function Sources({ sources }) {
  const [open, setOpen] = useState(null)
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((s, i) => (
          <button
            key={`${s.document_id}-${s.chunk_index}`}
            onClick={() => setOpen(open === i ? null : i)}
            className={`inline-flex min-h-[32px] max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
              open === i ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-600 hover:border-brand-200 hover:bg-brand-50/50'
            }`}
            aria-expanded={open === i}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-brand-100 text-[10px] font-semibold text-brand-700">
              {s.ref ?? i + 1}
            </span>
            <FileText className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{s.document_name}</span>
            <span className="shrink-0 text-slate-400">§{s.chunk_index + 1}</span>
          </button>
        ))}
      </div>
      <AnimatePresence>
        {open !== null && sources[open]?.snippet && (
          <motion.blockquote
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 overflow-hidden rounded-lg border-l-2 border-brand-400 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600"
          >
            “{sources[open].snippet}…”
          </motion.blockquote>
        )}
      </AnimatePresence>
    </div>
  )
}

function Feedback({ conversationId, initial }) {
  const [value, setValue] = useState(initial || null)
  const mutation = useMutation({
    mutationFn: (feedback) => api.put(`/conversations/${conversationId}/feedback`, { feedback }),
    onError: () => toast.error('Could not save feedback'),
  })
  const send = (v) => {
    const next = value === v ? null : v
    setValue(next)
    mutation.mutate(next)
    if (next) toast.success('Thanks for the feedback')
  }
  const btn = (v, Icon, label) => (
    <button
      onClick={() => send(v)}
      aria-label={label}
      aria-pressed={value === v}
      className={`flex h-9 w-9 items-center justify-center rounded-lg transition ${
        value === v ? 'bg-brand-50 text-brand-600' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600'
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  )
  return (
    <div className="mt-2 flex gap-1">
      {btn('thumbs_up', ThumbsUp, 'Helpful')}
      {btn('thumbs_down', ThumbsDown, 'Not helpful')}
    </div>
  )
}

function Composer({ value, onChange, onSend, onStop, streaming }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [value])

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSend()
      }}
      className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-card transition focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-100"
    >
      <textarea
        ref={ref}
        rows={1}
        value={value}
        maxLength={2000}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            onSend()
          }
        }}
        placeholder="Ask a question about your company…"
        aria-label="Your question"
        className="max-h-[180px] min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] text-slate-900 placeholder:text-slate-400 focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
      />
      {streaming ? (
        <button type="button" onClick={onStop} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white" aria-label="Stop generating">
          <Square className="h-4 w-4 fill-current" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={!value.trim()}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500 text-white transition hover:bg-brand-600 disabled:bg-slate-200 disabled:text-slate-400"
          aria-label="Send"
        >
          <ArrowUp className="h-5 w-5" />
        </button>
      )}
    </form>
  )
}

function UsageBanner({ usage, onClose }) {
  const admin = isAdmin(useAuth.getState().user)
  const text = usage.blocked
    ? 'Your organization has used all its questions for this month.'
    : `Your organization has used ${usage.used} of ${usage.limit} questions this month.`
  return (
    <div className="mb-2 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span className="flex-1">
        {text}{' '}
        {admin && (
          <Link to="/settings/plan" className="font-medium underline">
            Upgrade plan
          </Link>
        )}
      </span>
      <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded" aria-label="Dismiss">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

function HistoryPanel({ open, onClose, onSelect }) {
  const [q, setQ] = useState('')
  const [term, setTerm] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setTerm(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])
  const { data, isLoading } = useQuery({
    queryKey: ['conversations', term],
    queryFn: () => api.get('/conversations', { params: { limit: 50, q: term || undefined } }).then((r) => r.data),
  })

  const list = (
    <div className="flex h-full flex-col bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">Your history</h2>
        <button onClick={onClose} className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 xl:hidden" aria-label="Close history">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder="Search questions" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search history" />
        </div>
      </div>
      <ul className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading && <li className="px-3 py-6 text-center text-sm text-slate-400">Loading…</li>}
        {!isLoading && !data?.items?.length && (
          <li className="px-3 py-6 text-center text-sm text-slate-400">{q ? 'No matches.' : 'Questions you ask will appear here.'}</li>
        )}
        {data?.items?.map((c) => (
          <li key={c.id}>
            <button onClick={() => onSelect(c)} className="w-full rounded-lg px-3 py-2.5 text-left transition hover:bg-slate-50">
              <p className="line-clamp-2 text-sm text-slate-700">{c.question}</p>
              <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-400">
                {timeAgo(c.created_at)}
                {!c.is_answered && <span className="text-amber-600">· not found</span>}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )

  return (
    <>
      <aside className="hidden w-72 shrink-0 border-l border-slate-200 xl:block">{list}</aside>
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-40 xl:hidden">
            <motion.div className="absolute inset-0 bg-slate-900/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
            <motion.div
              className="absolute inset-y-0 right-0 w-80 max-w-[90vw] shadow-pop"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 400, damping: 40 }}
            >
              {list}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}
