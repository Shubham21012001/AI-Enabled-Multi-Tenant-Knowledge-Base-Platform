import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { AlertCircle, CloudUpload, FileText, MessageSquare, RotateCw, Search, Trash2 } from 'lucide-react'
import { api, errorMessage } from '../lib/api'
import { isAdmin, useAuth } from '../store/auth'
import { Badge, ConfirmModal, EmptyState, FileIcon, PageHeader, Spinner, formatBytes, formatDate } from '../components/ui'

const ACCEPT = '.pdf,.docx,.txt'
const MAX_MB = 10
const STATUS_LABEL = { ready: 'Ready', processing: 'Processing', uploading: 'Uploading', failed: 'Failed' }

export default function Documents() {
  const admin = isAdmin(useAuth((s) => s.user))
  const qc = useQueryClient()
  const [uploads, setUploads] = useState([]) // in-flight uploads with progress
  const [filter, setFilter] = useState('')
  const [toDelete, setToDelete] = useState(null)

  const { data: docs, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.get('/documents/').then((r) => r.data),
    // Poll while anything is still being processed, then stop.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === 'processing' || d.status === 'uploading') ? 2500 : false,
  })
  const { data: usage } = useQuery({
    queryKey: ['usage'],
    queryFn: () => api.get('/organizations/me/usage').then((r) => r.data),
  })

  const remove = useMutation({
    mutationFn: (id) => api.delete(`/documents/${id}`),
    onSuccess: () => {
      toast.success('Document deleted')
      qc.invalidateQueries({ queryKey: ['documents'] })
      qc.invalidateQueries({ queryKey: ['usage'] })
      setToDelete(null)
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  const reprocess = useMutation({
    mutationFn: (id) => api.post(`/documents/${id}/reprocess`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
    onError: (e) => toast.error(errorMessage(e)),
  })

  async function uploadFiles(files) {
    for (const file of files) {
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (!['pdf', 'docx', 'txt'].includes(ext)) {
        toast.error(`${file.name}: only PDF, DOCX and TXT are supported`)
        continue
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        toast.error(`${file.name} is larger than ${MAX_MB} MB`)
        continue
      }
      const key = `${file.name}-${Date.now()}-${Math.random()}`
      setUploads((u) => [...u, { key, name: file.name, type: ext, progress: 0 }])
      const body = new FormData()
      body.append('file', file)
      try {
        await api.post('/documents/upload', body, {
          onUploadProgress: (e) =>
            setUploads((u) => u.map((x) => (x.key === key ? { ...x, progress: e.total ? e.loaded / e.total : 0 } : x))),
        })
        toast.success(`${file.name} uploaded — processing now`)
      } catch (e) {
        toast.error(`${file.name}: ${errorMessage(e, 'upload failed')}`)
      } finally {
        setUploads((u) => u.filter((x) => x.key !== key))
        qc.invalidateQueries({ queryKey: ['documents'] })
        qc.invalidateQueries({ queryKey: ['usage'] })
        qc.invalidateQueries({ queryKey: ['org'] })
      }
    }
  }

  const docLimit = usage?.documents
  const atLimit = docLimit?.blocked
  const visible = (docs || []).filter((d) => d.original_filename.toLowerCase().includes(filter.toLowerCase()))

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      <PageHeader
        title="Documents"
        description="The knowledge KnowBot answers from. Only people in your organization can see these."
        actions={
          docLimit && (
            <div className="text-right text-xs text-slate-500">
              <span className="font-semibold text-slate-700">{docLimit.used}</span>
              {docLimit.limit !== null ? ` / ${docLimit.limit}` : ''} documents
            </div>
          )
        }
      />

      {admin && <DropZone onFiles={uploadFiles} disabled={atLimit} />}
      {atLimit && admin && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-amber-700">
          <AlertCircle className="h-4 w-4" /> You've reached your plan's document limit. Delete a document or upgrade your plan.
        </p>
      )}

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold text-slate-900">
          All documents {docs && <span className="font-normal text-slate-400">({docs.length})</span>}
        </h2>
        {docs?.length > 0 && (
          <div className="relative sm:w-64">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input className="input pl-9" placeholder="Filter by name" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter documents" />
          </div>
        )}
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="flex justify-center py-16"><Spinner className="h-6 w-6" /></div>
        ) : !docs?.length && !uploads.length ? (
          <div className="card">
            <EmptyState
              icon={FileText}
              title="No documents yet"
              description={admin ? 'Upload HR policies, SOPs, manuals or guides. KnowBot will index them in the background.' : 'Your admin hasn’t uploaded any documents yet.'}
            />
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <AnimatePresence initial={false}>
              {uploads.map((u) => (
                <motion.div key={u.key} layout initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="card p-4">
                  <div className="flex items-start gap-3">
                    <FileIcon type={u.type} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">{u.name}</p>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${Math.round(u.progress * 100)}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">Uploading… {Math.round(u.progress * 100)}%</p>
                    </div>
                  </div>
                </motion.div>
              ))}
              {visible.map((d) => (
                <DocumentCard
                  key={d.id}
                  doc={d}
                  admin={admin}
                  onDelete={() => setToDelete(d)}
                  onRetry={() => reprocess.mutate(d.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      <ConfirmModal
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={() => remove.mutate(toDelete.id)}
        loading={remove.isPending}
        title="Delete document?"
        message={toDelete && `“${toDelete.original_filename}” and its indexed content will be permanently removed. KnowBot will no longer use it to answer questions.`}
      />
    </div>
  )
}

function DropZone({ onFiles, disabled }) {
  const [over, setOver] = useState(false)
  const input = useRef(null)
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        if (!disabled) onFiles([...e.dataTransfer.files])
      }}
      className={`relative rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
        disabled
          ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60'
          : over
            ? 'border-brand-400 bg-brand-50'
            : 'border-slate-300 bg-white hover:border-brand-300'
      }`}
    >
      <motion.div animate={{ y: over ? -4 : 0 }} className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50">
        <CloudUpload className="h-6 w-6 text-brand-500" />
      </motion.div>
      <p className="text-sm font-medium text-slate-900">
        Drag & drop files here, or{' '}
        <button type="button" disabled={disabled} onClick={() => input.current?.click()} className="font-semibold text-brand-600 hover:text-brand-700">
          browse
        </button>
      </p>
      <p className="mt-1 text-xs text-slate-500">PDF, DOCX or TXT · up to {MAX_MB} MB each</p>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          onFiles([...e.target.files])
          e.target.value = ''
        }}
      />
    </div>
  )
}

function DocumentCard({ doc, admin, onDelete, onRetry }) {
  const busy = doc.status === 'processing' || doc.status === 'uploading'
  return (
    <motion.div layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }} className="card group flex flex-col p-4">
      <div className="flex items-start gap-3">
        <FileIcon type={doc.file_type} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900" title={doc.original_filename}>
            {doc.original_filename}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {doc.file_type.toUpperCase()} · {formatBytes(doc.file_size)} · {formatDate(doc.created_at)}
          </p>
        </div>
      </div>
      {doc.status === 'failed' && doc.error_message && (
        <p className="mt-3 rounded bg-red-50 px-2.5 py-1.5 text-xs text-red-700">{doc.error_message}</p>
      )}
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge tone={doc.status} pulse={busy}>{STATUS_LABEL[doc.status]}</Badge>
          {doc.status === 'ready' && (
            <span className="inline-flex items-center gap-1 text-xs text-slate-500" title="Questions answered using this document">
              <MessageSquare className="h-3.5 w-3.5" /> {doc.question_count}
            </span>
          )}
        </div>
        {admin && (
          <div className="flex gap-1">
            {doc.status === 'failed' && (
              <button onClick={onRetry} className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600" aria-label={`Retry ${doc.original_filename}`} title="Retry processing">
                <RotateCw className="h-4 w-4" />
              </button>
            )}
            <button onClick={onDelete} className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label={`Delete ${doc.original_filename}`} title="Delete">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}
