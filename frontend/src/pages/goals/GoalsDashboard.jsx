import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { goalsApi } from '../../api/goals'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'
import { useRole } from '../../context/RoleContext'

export default function GoalsDashboard() {
  const navigate = useNavigate()
  const toast = useToast()
  const { role } = useRole()
  const canManage = ['admin', 'manager', 'hr'].includes(role)
  const [goals, setGoals]     = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState('')

  useEffect(() => {
    goalsApi.getAll()
      .then(res => {
        const arr = Array.isArray(res) ? res : res?.items || res?.goals || []
        setGoals(arr)
      })
      .catch(err => toast.error('Failed to load', err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageLoader />

  const filtered = goals.filter(g =>
    !search || g.employee_name?.toLowerCase().includes(search.toLowerCase())
  )

  const pendingCount = goals.filter(g => g.pending_goal_update?.length > 0).length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Goals</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{filtered.length} records</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search employees..."
            style={{
              padding: '8px 12px', borderRadius: 8, fontSize: 13,
              border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-primary)', outline: 'none', width: 220,
            }}
          />
          {canManage && (
            <button onClick={() => navigate('/goals/new')} style={{
              padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
              color: '#fff', border: 'none', cursor: 'pointer',
              boxShadow: '0 0 14px rgba(99,102,241,0.25)',
            }}>+ Add Goal</button>
          )}
        </div>
      </div>

      {pendingCount > 0 && canManage && (
        <div style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 'var(--radius-lg)', padding: '12px 18px',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#F59E0B', boxShadow: '0 0 6px #F59E0B' }} />
          <span style={{ fontWeight: 500, color: '#F59E0B', fontSize: 13 }}>
            {pendingCount} goal update{pendingCount > 1 ? 's' : ''} pending your approval
          </span>
        </div>
      )}

      {filtered.length === 0 ? (
        <EmptyState message="No goals found" canManage={canManage} onAdd={() => navigate('/goals/new')} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {filtered.map((goal, i) => (
            <GoalCard
              key={i}
              goal={goal}
              onClick={() => navigate(`/goals/${encodeURIComponent(goal.employee_name)}/${encodeURIComponent(goal.review_period)}`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function GoalCard({ goal, onClick }) {
  const goalsList = goal.goals_set || goal.goals || []
  const achieved  = goal.goals_achieved || []
  const total     = goalsList.length
  const done      = achieved.length
  const pct       = total > 0 ? Math.round((done / total) * 100) : 0
  const color     = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444'
  const hasPending = goal.pending_goal_update?.length > 0

  return (
    <div onClick={onClick} style={{
      background: 'var(--color-bg-surface)', border: `1px solid ${hasPending ? 'rgba(245,158,11,0.4)' : 'var(--color-border)'}`,
      borderRadius: 'var(--radius-lg)', padding: '18px 20px',
      cursor: 'pointer', transition: 'box-shadow 0.15s', position: 'relative',
    }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = 'var(--shadow-md)'}
      onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
    >
      {hasPending && (
        <div style={{
          position: 'absolute', top: 12, right: 12,
          padding: '2px 8px', borderRadius: 20, fontSize: 10.5, fontWeight: 600,
          background: 'rgba(245,158,11,0.15)', color: '#F59E0B',
          border: '1px solid rgba(245,158,11,0.3)',
        }}>⚠ Pending</div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)' }}>{goal.employee_name || 'Unknown'}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{goal.review_period || '—'}</div>
        </div>
        <span style={{
          padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
          background: `${color}18`, color, border: `1px solid ${color}30`,
        }}>{done}/{total} done</span>
      </div>

      {goalsList.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
          {goalsList.slice(0, 3).map((g, i) => {
            const isDone = achieved.includes(g)
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{ color: isDone ? '#10B981' : 'var(--color-text-muted)', fontSize: 13, marginTop: 1, flexShrink: 0 }}>
                  {isDone ? '✓' : '○'}
                </span>
                <span style={{
                  fontSize: 12.5, lineHeight: 1.4,
                  color: isDone ? 'var(--color-text-secondary)' : 'var(--color-text-primary)',
                  textDecoration: isDone ? 'line-through' : 'none',
                  opacity: isDone ? 0.6 : 1,
                }}>
                  {typeof g === 'string' ? g : g.goal || JSON.stringify(g)}
                </span>
              </div>
            )
          })}
          {goalsList.length > 3 && (
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)', paddingLeft: 22 }}>
              +{goalsList.length - 3} more
            </span>
          )}
        </div>
      )}

      <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}

function EmptyState({ message, canManage, onAdd }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)', padding: 48, textAlign: 'center',
    }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>🏆</div>
      <div style={{ color: 'var(--color-text-muted)', fontSize: 14, marginBottom: canManage ? 16 : 0 }}>{message}</div>
      {canManage && (
        <button onClick={onAdd} style={{
          padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
          color: '#fff', border: 'none', cursor: 'pointer',
        }}>+ Add First Goal</button>
      )}
    </div>
  )
}