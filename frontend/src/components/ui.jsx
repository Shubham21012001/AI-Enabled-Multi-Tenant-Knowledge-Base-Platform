import { AnimatePresence, motion } from 'framer-motion'
import { FileText, FileType2, File, Loader2, X } from 'lucide-react'
import { useEffect } from 'react'

export function Spinner({ className = 'h-5 w-5' }) {
  return <Loader2 className={`animate-spin text-brand-500 ${className}`} aria-hidden="true" />
}

export function FullPageSpinner() {
  return (
    <div className="flex h-screen items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  )
}

export function Logo({ light = false, size = 'md' }) {
  const box = size === 'lg' ? 'h-10 w-10' : 'h-8 w-8'
  return (
    <div className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className={box} />
      <span className={`text-lg font-semibold tracking-tight ${light ? 'text-white' : 'text-slate-900'}`}>
        KnowBot
      </span>
    </div>
  )
}

const BADGE_STYLES = {
  ready: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  processing: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  uploading: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  failed: 'bg-red-50 text-red-700 ring-red-600/20',
  admin: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  member: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  neutral: 'bg-slate-100 text-slate-700 ring-slate-500/20',
}

export function Badge({ tone = 'neutral', children, pulse = false }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${BADGE_STYLES[tone] || BADGE_STYLES.neutral}`}
    >
      {pulse && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {children}
    </span>
  )
}

const FILE_STYLES = {
  pdf: { icon: FileText, cls: 'bg-red-50 text-red-600' },
  docx: { icon: FileType2, cls: 'bg-blue-50 text-blue-600' },
  txt: { icon: File, cls: 'bg-slate-100 text-slate-600' },
}

export function FileIcon({ type, className = 'h-10 w-10' }) {
  const { icon: Icon, cls } = FILE_STYLES[type] || FILE_STYLES.txt
  return (
    <div className={`flex shrink-0 items-center justify-center rounded-lg ${cls} ${className}`}>
      <Icon className="h-5 w-5" aria-hidden="true" />
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      {Icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50">
          <Icon className="h-6 w-6 text-brand-500" />
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ProgressBar({ percent, warning, blocked, className = '' }) {
  const color = blocked ? 'bg-red-500' : warning ? 'bg-amber-500' : 'bg-brand-500'
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-slate-100 ${className}`}>
      <motion.div
        className={`h-full rounded-full ${color}`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(percent, 100)}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      />
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
          <motion.div
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="relative w-full max-w-md rounded-t-xl bg-white shadow-pop sm:rounded-lg"
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <h2 className="text-base font-semibold text-slate-900">{title}</h2>
              <button onClick={onClose} className="btn-ghost -mr-2 px-2" aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="px-5 py-4">{children}</div>
            {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export function ConfirmModal({ open, onClose, onConfirm, title, message, confirmLabel = 'Delete', loading }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-danger" onClick={onConfirm} disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-600">{message}</p>
    </Modal>
  )
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatDate(iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) {
  return new Date(iso).toLocaleDateString(undefined, opts)
}

export function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`
  return formatDate(iso)
}
