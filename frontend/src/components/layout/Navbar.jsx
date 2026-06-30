import { useLocation, useNavigate } from 'react-router-dom'
import { useRole } from '../../context/RoleContext'

const ROUTE_LABELS = {
  '/dashboard':     'Dashboard',
  '/employees':     'Employees',
  '/candidates':    'Candidates',
  '/products':      'Products',
  '/goals':         'Goals',
  '/roles':         'Roles',
  '/workflows':     'Workflows',
  '/approvals':     'Approvals',
  '/reporting':     'Reports & Analytics',
  '/notifications': 'Notifications',
  '/unauthorized':  'Access Restricted',
}

function getLabel(pathname) {
  const match = Object.keys(ROUTE_LABELS)
    .sort((a, b) => b.length - a.length)
    .find(key => pathname.startsWith(key))
  return ROUTE_LABELS[match] || 'AI Digital Employee'
}

export default function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { userName, role } = useRole()
  const label = getLabel(location.pathname)
  const initials = userName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()

  return (
    <header style={{
      position: 'fixed', top: 0, left: 'var(--sidebar-width)', right: 0,
      height: 'var(--navbar-height)',
      background: 'rgba(9,14,26,0.85)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderBottom: '1px solid var(--color-border)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 24px', zIndex: 99,
    }}>
      <h1 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', letterSpacing: '-0.01em' }}>
        {label}
      </h1>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {/* Role pill */}
        <span style={{
          padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
          textTransform: 'uppercase', letterSpacing: '0.05em',
          background: role === 'manager' ? 'rgba(99,102,241,0.15)' : 'rgba(16,185,129,0.12)',
          color: role === 'manager' ? '#818CF8' : '#10B981',
          border: `1px solid ${role === 'manager' ? 'rgba(99,102,241,0.3)' : 'rgba(16,185,129,0.25)'}`,
        }}>
          {role}
        </span>

        {/* Bell */}
        <button
          onClick={() => navigate('/notifications')}
          style={{
            width: 32, height: 32, borderRadius: 8,
            border: '1px solid var(--color-border)',
            background: 'var(--color-bg-elevated)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: 'var(--color-text-secondary)',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
        </button>

        {/* Avatar */}
        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontWeight: 600, fontSize: 11,
          cursor: 'pointer', userSelect: 'none',
          boxShadow: '0 0 10px rgba(99,102,241,0.35)',
          title: userName,
        }}>
          {initials}
        </div>
      </div>
    </header>
  )
}