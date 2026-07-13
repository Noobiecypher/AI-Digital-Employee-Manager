import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationsApi } from '../api/notifications'
import { PageLoader } from '../components/ui/LoadingSpinner'
import { useToast } from '../components/layout/AppLayout'

const TYPE_META = {
  workflow_started:   { icon: '▶️', color: '#6366F1', bg: 'rgba(99,102,241,0.10)'  },
  workflow_paused:    { icon: '⏸️', color: '#F59E0B', bg: 'rgba(245,158,11,0.10)'  },
  workflow_approved:  { icon: '✅', color: '#10B981', bg: 'rgba(16,185,129,0.10)'  },
  workflow_rejected:  { icon: '❌', color: '#EF4444', bg: 'rgba(239,68,68,0.10)'   },
  workflow_completed: { icon: '🎉', color: '#10B981', bg: 'rgba(16,185,129,0.10)'  },
  workflow_failed:    { icon: '⚠️', color: '#EF4444', bg: 'rgba(239,68,68,0.10)'   },
  goal_assigned:      { icon: '🎯', color: '#6366F1', bg: 'rgba(99,102,241,0.10)'  },
  goal_submitted:     { icon: '📋', color: '#F59E0B', bg: 'rgba(245,158,11,0.10)'  },
  goal_approved:      { icon: '✅', color: '#10B981', bg: 'rgba(16,185,129,0.10)'  },
  goal_rejected:      { icon: '❌', color: '#EF4444', bg: 'rgba(239,68,68,0.10)'   },
}

function timeAgo(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins < 1)   return 'just now'
  if (mins < 60)  return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

export default function Notifications() {
  const navigate = useNavigate()
  const toast    = useToast()
  const [items, setItems]     = useState([])
  const [loading, setLoading] = useState(true)
  const [unread, setUnread]   = useState(0)

  const load = async () => {
    try {
      const res = await notificationsApi.getAll()
      setItems(res?.items || [])
      setUnread(res?.unread || 0)
    } catch (err) {
      toast.error('Failed to load notifications', err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleClick = async (notif) => {
    if (!notif.read) {
      await notificationsApi.markRead(notif.notification_id).catch(() => {})
      setItems(prev => prev.map(n => n.notification_id === notif.notification_id ? { ...n, read: true } : n))
      setUnread(u => Math.max(0, u - 1))
    }
    if (notif.link) navigate(notif.link)
  }

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead().catch(() => {})
    setItems(prev => prev.map(n => ({ ...n, read: true })))
    setUnread(0)
  }

  if (loading) return <PageLoader />

  return (
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: 10 }}>
            Notifications
            {unread > 0 && (
              <span style={{
                padding: '1px 8px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                background: '#6366F1', color: '#fff',
              }}>{unread}</span>
            )}
          </h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
            Workflow updates, approvals, and goal alerts
          </p>
        </div>
        {unread > 0 && (
          <button onClick={handleMarkAllRead} style={{
            padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
            border: '1px solid var(--color-border)', background: 'transparent',
            color: 'var(--color-text-secondary)', cursor: 'pointer',
          }}>Mark all read</button>
        )}
      </div>

      {items.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 48, textAlign: 'center',
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🔔</div>
          <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--color-text-primary)', marginBottom: 6 }}>No notifications yet</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Workflow completions, approval requests, and goal alerts will appear here.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.map(notif => {
            const meta = TYPE_META[notif.type] || { icon: '🔔', color: '#6366F1', bg: 'rgba(99,102,241,0.10)' }
            return (
              <div
                key={notif.notification_id}
                onClick={() => handleClick(notif)}
                style={{
                  display: 'flex', gap: 14, alignItems: 'flex-start',
                  padding: '14px 18px', borderRadius: 'var(--radius-lg)',
                  background: notif.read ? 'var(--color-bg-surface)' : 'rgba(99,102,241,0.04)',
                  border: `1px solid ${notif.read ? 'var(--color-border)' : 'rgba(99,102,241,0.2)'}`,
                  cursor: notif.link ? 'pointer' : 'default',
                  transition: 'box-shadow 0.15s',
                  position: 'relative',
                }}
                onMouseEnter={e => { if (notif.link) e.currentTarget.style.boxShadow = 'var(--shadow-md)' }}
                onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
              >
                {/* Unread dot */}
                {!notif.read && (
                  <div style={{
                    position: 'absolute', top: 16, right: 16,
                    width: 8, height: 8, borderRadius: '50%',
                    background: '#6366F1', boxShadow: '0 0 6px #6366F1',
                  }} />
                )}

                {/* Icon */}
                <div style={{
                  width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                  background: meta.bg, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 18,
                }}>{meta.icon}</div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: notif.read ? 500 : 700,
                    fontSize: 13.5, color: 'var(--color-text-primary)', marginBottom: 3,
                  }}>{notif.title}</div>
                  <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                    {notif.message}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 6 }}>
                    {timeAgo(notif.created_at)}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}