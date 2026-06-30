import { createContext, useContext, useState } from 'react'

const RoleContext = createContext(null)

export const ROLES = {
  MANAGER:  'manager',
  EMPLOYEE: 'employee',
}

export function RoleProvider({ children }) {
  const [role, setRole] = useState(ROLES.MANAGER)
  const [userName, setUserName] = useState('Abhinav Muley')

  const isManager  = role === ROLES.MANAGER
  const isEmployee = role === ROLES.EMPLOYEE

  return (
    <RoleContext.Provider value={{ role, setRole, userName, setUserName, isManager, isEmployee }}>
      {children}
    </RoleContext.Provider>
  )
}

export function useRole() {
  const ctx = useContext(RoleContext)
  if (!ctx) throw new Error('useRole must be used inside RoleProvider')
  return ctx
}

// Which pages each role can access
export const ROLE_PERMISSIONS = {
  manager: [
    '/dashboard', '/notifications', '/employees', '/candidates',
    '/products', '/goals', '/roles', '/workflows', '/approvals', '/reporting',
  ],
  employee: [
    '/dashboard', '/notifications', '/goals',
  ],
}

export function canAccess(role, pathname) {
  const allowed = ROLE_PERMISSIONS[role] || []
  return allowed.some(p => pathname === p || pathname.startsWith(p + '/'))
}