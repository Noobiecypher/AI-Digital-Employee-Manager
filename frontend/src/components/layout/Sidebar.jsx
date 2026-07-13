import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useRole, canAccess } from '../../context/RoleContext'
import { useState, useEffect, useRef } from 'react'
import { notificationsApi } from '../../api/notifications'

// SVG Icons
function GridIcon()      { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg> }
function BellIcon()      { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg> }
function UsersIcon()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> }
function TargetIcon()    { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg> }
function BoxIcon()       { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg> }
function FlagIcon()      { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg> }
function LayersIcon()    { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg> }
function ZapIcon()       { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> }
function CheckIcon()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg> }
function ChartIcon()     { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> }
function BriefcaseIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg> }
function FileIcon()      { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> }

// Full nav list — filtered per-role at render time using canAccess()
const ALL_NAV = [
  {
    section: 'Overview',
    items: [
      { to: '/dashboard',     label: 'Dashboard',     icon: <GridIcon /> },
      { to: '/notifications', label: 'Notifications', icon: <BellIcon /> },
    ]
  },
  {
    section: 'People',
    items: [
      { to: '/employees',  label: 'Employees',  icon: <UsersIcon /> },
      { to: '/candidates', label: 'Candidates', icon: <TargetIcon /> },
      { to: '/jobs',       label: 'Jobs',       icon: <BriefcaseIcon /> },
    ]
  },
  {
    section: 'Business',
    items: [
      { to: '/products', label: 'Products', icon: <BoxIcon /> },
      { to: '/goals',    label: 'Goals',    icon: <FlagIcon /> },
      { to: '/roles',    label: 'Roles',    icon: <LayersIcon /> },
    ]
  },
  {
    section: 'Automation',
    items: [
      { to: '/workflows', label: 'Workflows', icon: <ZapIcon /> },
      { to: '/approvals', label: 'Approvals', icon: <CheckIcon /> },
    ]
  },
  {
    section: 'Documents',
    items: [
      { to: '/documents', label: 'Documents', icon: <FileIcon /> },
    ]
  },
  {
    section: 'Analytics',
    items: [
      { to: '/reporting', label: 'Reports', icon: <ChartIcon /> },
    ]
  },
]

const ROLE_COLORS = {
  admin:     '#EF4444',
  manager:   '#6366F1',
  hr:        '#06B6D4',
  employee:  '#10B981',
  candidate: '#F59E0B',
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { role, userName, logout } = useRole()
  const roleColor = ROLE_COLORS[role] || '#6366F1'

  const [unread, setUnread] = useState(0)
  const intervalRef = useRef(null)

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await notificationsApi.getAll()
        setUnread(res?.unread || 0)
      } catch {}
    }
    fetch()
    intervalRef.current = setInterval(fetch, 30000)
    return () => clearInterval(intervalRef.current)
  }, [])

  useEffect(() => {
    if (location.pathname === '/notifications') setUnread(0)
  }, [location.pathname])

  // Filter nav sections/items based on what this role can actually access
  const nav = ALL_NAV
    .map(group => ({
      ...group,
      items: group.items.filter(item => canAccess(role, item.to)),
    }))
    .filter(group => group.items.length > 0)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside style={{
      width: 'var(--sidebar-width)',
      background: 'var(--color-bg-sidebar)',
      borderRight: '1px solid var(--color-border)',
      position: 'fixed',
      top: 0, left: 0, bottom: 0,
      display: 'flex', flexDirection: 'column',
      zIndex: 100,
      overflowY: 'auto',
    }}>
      {/* Logo */}
      <div style={{
        padding: '18px 16px 16px',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{
          width: 28, height: 28,
          background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
          borderRadius: 7,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: '#fff', flexShrink: 0,
          boxShadow: '0 0 12px rgba(99,102,241,0.4)',
        }}>AI</div>
        <div>
          <div style={{ color: 'var(--color-text-primary)', fontWeight: 600, fontSize: 13, lineHeight: 1.2 }}>AI Employee</div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: 10.5, lineHeight: 1.3 }}>Platform</div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '4px 0' }}>
        {nav.map(group => (
          <div key={group.section}>
            <div style={{
              padding: '12px 16px 4px',
              fontSize: 9.5, fontWeight: 600,
              letterSpacing: '0.1em', textTransform: 'uppercase',
              color: 'var(--color-text-muted)',
            }}>
              {group.section}
            </div>
            {group.items.map(item => (
              <SidebarLink
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
                badge={item.to === '/notifications' ? unread : 0}
              />
            ))}
          </div>
        ))}
      </nav>

      {/* Sign out */}
      <div style={{ padding: '12px', borderTop: '1px solid var(--color-border)' }}>
        <button
          onClick={handleLogout}
          style={{
            width: '100%', padding: '8px 12px', borderRadius: 8, fontSize: 12.5, fontWeight: 500,
            border: '1px solid rgba(239,68,68,0.25)', background: 'rgba(239,68,68,0.08)',
            color: '#EF4444', cursor: 'pointer', transition: 'all 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.15)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(239,68,68,0.08)'}
        >
          Sign Out
        </button>
        <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 8, paddingLeft: 2 }}>
          v1.0.0 · BITS Pilani
        </div>
      </div>
    </aside>
  )
}

function SidebarLink({ to, label, icon, badge = 0 }) {
  const location = useLocation()
  const isActive = location.pathname === to || (to !== '/dashboard' && location.pathname.startsWith(to))

  return (
    <NavLink
      to={to}
      style={{
        display: 'flex', alignItems: 'center', gap: 9,
        padding: '7px 12px', margin: '1px 8px', borderRadius: 7,
        fontSize: 13, fontWeight: isActive ? 500 : 400,
        color: isActive ? '#fff' : 'var(--color-text-sidebar)',
        background: isActive ? 'var(--color-primary-light)' : 'transparent',
        borderLeft: `2px solid ${isActive ? 'var(--color-primary)' : 'transparent'}`,
        transition: 'all 0.12s', textDecoration: 'none',
        justifyContent: 'space-between',
      }}
      onMouseEnter={e => { if (!isActive) { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--color-text-primary)' }}}
      onMouseLeave={e => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-sidebar)' }}}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <span style={{ opacity: isActive ? 1 : 0.6, display: 'flex', alignItems: 'center' }}>{icon}</span>
        {label}
      </div>
      {badge > 0 && (
        <span style={{
          minWidth: 18, height: 18, borderRadius: 9,
          background: '#EF4444', color: '#fff',
          fontSize: 10, fontWeight: 700,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '0 4px', boxShadow: '0 0 6px rgba(239,68,68,0.5)',
          lineHeight: 1, flexShrink: 0,
        }}>
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </NavLink>
  )
}