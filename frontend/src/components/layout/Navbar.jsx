import { useLocation, useNavigate } from 'react-router-dom'
import { useRole } from '../../context/RoleContext'
import { useState, useEffect, useRef } from 'react'
import { notificationsApi } from '../../api/notifications'

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

const ROLE_STYLES = {
  admin:     { bg: 'rgba(239,68,68,0.12)',   color: '#EF4444', border: 'rgba(239,68,68,0.3)'    },
  manager:   { bg: 'rgba(99,102,241,0.15)',  color: '#818CF8', border: 'rgba(99,102,241,0.3)'   },
  hr:        { bg: 'rgba(6,182,212,0.12)',   color: '#06B6D4', border: 'rgba(6,182,212,0.3)'    },
  employee:  { bg: 'rgba(16,185,129,0.12)',  color: '#10B981', border: 'rgba(16,185,129,0.25)'  },
  candidate: { bg: 'rgba(245,158,11,0.12)',  color: '#F59E0B', border: 'rgba(245,158,11,0.25)'  },
}

export default function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { userName, role } = useRole()
  const label    = getLabel(location.pathname)
  const initials = userName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
  const roleStyle = ROLE_STYLES[role] || ROLE_STYLES.manager

  const [unread, setUnread] = useState(0)
  const intervalRef = useRef(null)

  const fetchUnread = async () => {
    try {
      const res = await notificationsApi.getAll()
      setUnread(res?.unread || 0)
    } catch {}
  }

  useEffect(() => {
    fetchUnread()
    intervalRef.current = setInterval(fetchUnread, 30000) // poll every 30s
    return () => clearInterval(intervalRef.current)
  }, [])

  // Reset badge when user visits notifications page
  useEffect(() => {
    if (location.pathname === '/notifications') {
      setUnread(0)
    }
  }, [location.pathname])

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
          background: roleStyle.bg, color: roleStyle.color,
          border: `1px solid ${roleStyle.border}`,
        }}>
          {role}
        </span>

        {/* Bell with unread badge */}
        <button
          onClick={() => navigate('/notifications')}
          style={{
            width: 32, height: 32, borderRadius: 8,
            border: '1px solid var(--color-border)',
            background: 'var(--color-bg-elevated)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: 'var(--color-text-secondary)',
            position: 'relative',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
          {unread > 0 && (
            <span style={{
              position: 'absolute', top: -4, right: -4,
              minWidth: 16, height: 16, borderRadius: 8,
              background: '#EF4444', color: '#fff',
              fontSize: 9, fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: '0 3px', boxShadow: '0 0 6px rgba(239,68,68,0.6)',
              lineHeight: 1,
            }}>
              {unread > 99 ? '99+' : unread}
            </span>
          )}
        </button>

        {/* Avatar */}
        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontWeight: 600, fontSize: 11,
          cursor: 'pointer', userSelect: 'none',
          boxShadow: '0 0 10px rgba(99,102,241,0.35)',
        }}>
          {initials}
        </div>
      </div>
    </header>
  )
}