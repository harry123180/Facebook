import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../context/AuthContext'
import { FullPageSpinner } from './Feedback'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <FullPageSpinner />

  if (!user) {
    // 記住原路徑，登入後跳回
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  }

  return <>{children}</>
}
