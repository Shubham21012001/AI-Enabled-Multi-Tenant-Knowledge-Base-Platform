import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Bell, CheckCircle2, Info, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import { timeAgo } from './ui'

const ICONS = {
  document_ready: { icon: CheckCircle2, cls: 'text-emerald-500' },
  document_failed: { icon: XCircle, cls: 'text-red-500' },
  usage_warning: { icon: AlertTriangle, cls: 'text-amber-500' },
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get('/notifications').then((r) => r.data),
    refetchInterval: 30_000,
  })
  const readAll = useMutation({
    mutationFn: () => api.post('/notifications/read-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  useEffect(() => {
    if (!open) return
    const onClick = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const unread = data?.unread || 0

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex h-11 w-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100"
        aria-label={`Notifications${unread ? ` (${unread} unread)` : ''}`}
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-2 top-2 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-brand-500 px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 z-30 mt-2 w-[min(22rem,calc(100vw-1rem))] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-pop"
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
              <span className="text-sm font-semibold text-slate-900">Notifications</span>
              {unread > 0 && (
                <button onClick={() => readAll.mutate()} className="min-h-[44px] text-xs font-medium text-brand-600 hover:text-brand-700">
                  Mark all read
                </button>
              )}
            </div>
            <ul className="max-h-96 overflow-y-auto">
              {!data?.items?.length && <li className="px-4 py-8 text-center text-sm text-slate-500">You're all caught up.</li>}
              {data?.items?.map((n) => {
                const { icon: Icon, cls } = ICONS[n.type] || { icon: Info, cls: 'text-brand-500' }
                return (
                  <li key={n.id} className={`flex gap-3 border-b border-slate-50 px-4 py-3 last:border-0 ${n.is_read ? '' : 'bg-brand-50/40'}`}>
                    <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900">{n.title}</p>
                      <p className="mt-0.5 break-words text-xs text-slate-500">{n.message}</p>
                      <p className="mt-1 text-[11px] text-slate-400">{timeAgo(n.created_at)}</p>
                    </div>
                  </li>
                )
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
