import { NavLink, Navigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Building2, CreditCard, KeyRound, User, Users } from 'lucide-react'
import { isAdmin, useAuth } from '../../store/auth'
import { PageHeader } from '../../components/ui'
import ProfileTab from './ProfileTab'
import OrganizationTab from './OrganizationTab'
import MembersTab from './MembersTab'
import ApiKeysTab from './ApiKeysTab'
import PlanTab from './PlanTab'

const TABS = [
  { id: 'profile', label: 'Profile', icon: User, Component: ProfileTab },
  { id: 'organization', label: 'Organization', icon: Building2, Component: OrganizationTab },
  { id: 'members', label: 'Members', icon: Users, Component: MembersTab },
  { id: 'api-keys', label: 'API Keys', icon: KeyRound, Component: ApiKeysTab, adminOnly: true },
  { id: 'plan', label: 'Plan', icon: CreditCard, Component: PlanTab, adminOnly: true },
]

export default function Settings() {
  const { tab } = useParams()
  const admin = isAdmin(useAuth((s) => s.user))
  const tabs = TABS.filter((t) => !t.adminOnly || admin)
  const current = tabs.find((t) => t.id === tab)
  if (!current) return <Navigate to="/settings/profile" replace />
  const { Component } = current

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:py-8">
      <PageHeader title="Settings" description="Manage your profile and workspace." />
      <nav className="-mx-4 mb-6 overflow-x-auto border-b border-slate-200 px-4 sm:mx-0 sm:px-0" aria-label="Settings sections">
        <div className="flex min-w-max gap-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <NavLink
              key={id}
              to={`/settings/${id}`}
              className={({ isActive }) =>
                `relative flex min-h-[44px] items-center gap-2 px-3 text-sm font-medium transition-colors ${
                  isActive ? 'text-brand-600' : 'text-slate-500 hover:text-slate-800'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className="h-4 w-4" />
                  {label}
                  {isActive && <motion.span layoutId="settings-tab" className="absolute inset-x-0 -bottom-px h-0.5 bg-brand-500" />}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
      <motion.div key={current.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
        <Component admin={admin} />
      </motion.div>
    </div>
  )
}

export function Section({ title, description, children, footer }) {
  return (
    <section className="card">
      <div className="border-b border-slate-100 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
      </div>
      <div className="px-5 py-5">{children}</div>
      {footer && <div className="flex justify-end gap-2 rounded-b-lg border-t border-slate-100 bg-slate-50/60 px-5 py-3">{footer}</div>}
    </section>
  )
}
