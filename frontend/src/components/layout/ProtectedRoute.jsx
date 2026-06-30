import { Navigate, useLocation } from 'react-router-dom'
import { useRole, canAccess } from '../../context/RoleContext'

export default function ProtectedRoute({ children, managerOnly = false }) {
  const { role } = useRole()
  const location = useLocation()

  // Use the real permission matrix
  if (!canAccess(role, location.pathname)) {
    return <Navigate to="/unauthorized" replace state={{ from: location }} />
  }

  return children
}