import { Link } from 'react-router-dom'
import { Logo } from '../components/ui'

export default function NotFound() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center px-4 text-center">
      <Logo size="lg" />
      <p className="mt-10 text-sm font-semibold text-brand-600">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-500">The page you’re looking for doesn’t exist or was moved.</p>
      <Link to="/chat" className="btn-primary mt-6">Back to KnowBot</Link>
    </div>
  )
}
