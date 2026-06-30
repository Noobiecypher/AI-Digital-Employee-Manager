import { createContext, useContext, useState, useEffect } from 'react'

const RoleContext = createContext(null)

export const ROLES = {
  ADMIN:     'admin',
  MANAGER:   'manager',
  HR:        'hr',
  EMPLOYEE:  'employee',
  CANDIDATE: 'candidate',
}

export function RoleProvider({ children }) {
  const [user, setUser]   = useState(null)
  const [token, setToken] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token')
    const storedUser  = localStorage.getItem('auth_user')
    if (storedToken && storedUser) {
      setToken(storedToken)
      setUser(JSON.parse(storedUser))
    }
    setReady(true)
  }, [])

  const login = (accessToken, userData) => {
    localStorage.setItem('auth_token', accessToken)
    localStorage.setItem('auth_user', JSON.stringify(userData))
    setToken(accessToken)
    setUser(userData)
  }

  const logout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    setToken(null)
    setUser(null)
  }

  const role     = user?.role || null
  const userName = user?.username || user?.email || 'Guest'

  return (
    <RoleContext.Provider value={{
      user, token, role, userName, ready,
      isAuthenticated: !!token,
      isAdmin:     role === ROLES.ADMIN,
      isManager:   role === ROLES.MANAGER,
      isHR:        role === ROLES.HR,
      isEmployee:  role === ROLES.EMPLOYEE,
      isCandidate: role === ROLES.CANDIDATE,
      login, logout,
    }}>
      {children}
    </RoleContext.Provider>
  )
}

export function useRole() {
  const ctx = useContext(RoleContext)
  if (!ctx) throw new Error('useRole must be used inside RoleProvider')
  return ctx
}

// Based on the access matrix you shared
export const ROLE_PERMISSIONS = {
  admin: [
    '/dashboard', '/notifications', '/employees', '/candidates', '/jobs',
    '/products', '/goals', '/roles', '/workflows', '/approvals', '/reporting',
  ],
  manager: [
    '/dashboard', '/notifications', '/candidates', '/jobs',
    '/products', '/goals', '/workflows', '/approvals', '/reporting',
  ],
  hr: [
    '/dashboard', '/notifications', '/employees', '/candidates', '/jobs',
    '/goals', '/workflows', '/approvals', '/reporting',
  ],
  employee: [
    '/dashboard', '/notifications', '/goals',
  ],
  candidate: [
    '/dashboard',
  ],
}

export function canAccess(role, pathname) {
  const allowed = ROLE_PERMISSIONS[role] || []
  return allowed.some(p => pathname === p || pathname.startsWith(p + '/'))
}