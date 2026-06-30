import { Navigate, useLocation } from 'react-router-dom'
import { useRole } from '../../context/RoleContext'

export default function RequireAuth({ children }) {
  const { isAuthenticated, ready } = useRole()
  const location = useLocation()

  if (!ready) return null
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />

  return children
}