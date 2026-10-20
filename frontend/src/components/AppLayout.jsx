import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, FileText, LogOut, Menu, MessageSquare, Settings, X } from 'lucide-react'
import { api } from '../lib/api'
import { logout } from '../lib/session'
import { isAdmin, useAuth } from '../store/auth'
import { Logo } from './ui'
import NotificationBell from './NotificationBell'

const NAV = [
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3, adminOnly: true },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function initials(name = '') {
  return name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function SidebarContent({ onNavigate }) {
  const user = useAuth((s) => s.user)
  const { data: org } = useQuery({ queryKey: ['org'], queryFn: () => api.get('/organizations/me').then((r) => r.data) })
  const items = NAV.filter((n) => !n.adminOnly || isAdmin(user))

  return (
    <div className="flex h-full flex-col bg-sidebar text-white">
      <div className="flex h-16 items-center px-5">
        <Logo light />
      </div>

      {org && (
        <div className="mx-3 mb-4 rounded-lg bg-white/5 px-3 py-2.5">
          <p className="truncate text-sm font-medium text-white">{org.name}</p>
          <p className="text-xs capitalize text-sidebar-muted">{org.plan} plan</p>
        </div>
      )}

      <nav className="flex-1 space-y-1 px-3" aria-label="Main">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `group relative flex min-h-[44px] items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors ${
                isActive ? 'bg-sidebar-active text-white' : 'text-indigo-200 hover:bg-sidebar-hover hover:text-white'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-brand-400"
                  />
                )}
                <Icon className="h-5 w-5 shrink-0" />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500 text-sm font-semibold">
            {initials(user?.full_name)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user?.full_name}</p>
            <p className="truncate text-xs text-sidebar-muted">{user?.email}</p>
          </div>
          <button
            onClick={logout}
            className="flex h-11 w-11 items-center justify-center rounded-lg text-indigo-200 hover:bg-sidebar-hover hover:text-white"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AppLayout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setOpen(false), [location.pathname])

  return (
    <div className="flex h-[100dvh] overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 lg:block">
        <SidebarContent />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div
              className="absolute inset-0 bg-slate-900/50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              className="absolute inset-y-0 left-0 w-72 max-w-[85vw]"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 400, damping: 40 }}
            >
              <SidebarContent onNavigate={() => setOpen(false)} />
              <button
                onClick={() => setOpen(false)}
                className="absolute right-2 top-3 flex h-11 w-11 items-center justify-center rounded-lg text-indigo-200"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-2 sm:px-4 lg:justify-end">
          <button
            className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="lg:hidden">
            <Logo />
          </div>
          <NotificationBell />
        </header>
        <main className="relative min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
