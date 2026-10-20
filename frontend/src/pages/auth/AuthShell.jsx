import { motion } from 'framer-motion'
import { FileSearch, Lock, Quote, Zap } from 'lucide-react'
import { Logo } from '../../components/ui'

const POINTS = [
  { icon: FileSearch, text: 'Answers grounded in your own documents, with citations' },
  { icon: Lock, text: 'Every company’s data is fully isolated' },
  { icon: Zap, text: 'Streaming answers in seconds' },
]

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-[100dvh]">
      <div className="relative hidden w-[44%] overflow-hidden bg-sidebar lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-500/30 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-40 -left-20 h-96 w-96 rounded-full bg-brand-400/20 blur-3xl"
          aria-hidden="true"
        />
        <Logo light size="lg" />
        <div className="relative">
          <h2 className="max-w-md text-3xl font-semibold leading-tight tracking-tight text-white">
            Your company’s knowledge, one question away.
          </h2>
          <ul className="mt-8 space-y-4">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-indigo-100">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="text-sm">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <figure className="relative rounded-lg border border-white/10 bg-white/5 p-5">
          <Quote className="h-5 w-5 text-brand-300" />
          <blockquote className="mt-2 text-sm leading-relaxed text-indigo-100">
            “How many days of leave carry over?” — answered from the HR handbook, with the exact source, in two
            seconds.
          </blockquote>
        </figure>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="w-full max-w-sm"
        >
          <div className="mb-8 lg:hidden">
            <Logo size="lg" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-center text-sm text-slate-500">{footer}</div>}
        </motion.div>
      </div>
    </div>
  )
}

export function Field({ label, error, children, hint }) {
  return (
    <div>
      <label className="label">
        {label}
        {children}
      </label>
      {hint && !error && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function FormError({ message }) {
  if (!message) return null
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700">
      {message}
    </div>
  )
}
