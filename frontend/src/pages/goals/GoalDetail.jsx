import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { goalsApi } from '../../api/goals'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'
import { useRole } from '../../context/RoleContext'

export default function GoalDetail() {
  const { employee_name, period } = useParams()
  const navigate  = useNavigate()
  const toast     = useToast()
  const { user }  = useRole()
  const isManager = user?.role === 'manager' || user?.role === 'admin' || user?.role === 'hr'

  const [goal, setGoal]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editGoals, setEditGoals]   = useState('')
  const [comments, setComments]     = useState('')
  const [saving, setSaving]         = useState(false)
  const [approving, setApproving]   = useState(false)

  const load = () => {
    goalsApi.getOne(decodeURIComponent(employee_name), decodeURIComponent(period))
      .then(data => {
        setGoal(data)
        setEditGoals((data.goals_set || []).join('\n'))
      })
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [employee_name, period])

  const handleSaveEdit = async () => {
    setSaving(true)
    try {
      const newGoals = editGoals.split('\n').map(s => s.trim()).filter(Boolean)
      await goalsApi.update(
        decodeURIComponent(employee_name),
        decodeURIComponent(period),
        { goals_set: newGoals, pending_goal_update: newGoals }
      )
      toast.success('Goals updated', 'Pending manager approval')
      setEditing(false)
      load()
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    setApproving(true)
    try {
      await goalsApi.update(
        decodeURIComponent(employee_name),
        decodeURIComponent(period),
        {
          goals_set:            goal.pending_goal_update || goal.goals_set,
          pending_goal_update:  null,
          approved_by:          user?.username || 'Manager',
          approved_at:          new Date().toISOString(),
          manager_comments:     comments || null,
        }
      )
      toast.success('Goals approved')
      setComments('')
      load()
    } catch (err) {
      toast.error('Approval failed', err.message)
    } finally {
      setApproving(false)
    }
  }

  const handleReject = async () => {
    setApproving(true)
    try {
      await goalsApi.update(
        decodeURIComponent(employee_name),
        decodeURIComponent(period),
        {
          pending_goal_update: null,
          manager_comments:    comments || 'Rejected by manager',
        }
      )
      toast.success('Goal update rejected')
      setComments('')
      load()
    } catch (err) {
      toast.error('Failed', err.message)
    } finally {
      setApproving(false)
    }
  }

  if (loading) return <PageLoader />
  if (!goal) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Goal not found</div>

  const goalsList = goal.goals_set || []
  const achieved  = goal.goals_achieved || []
  const total     = goalsList.length
  const done      = achieved.length
  const pct       = total > 0 ? Math.round((done / total) * 100) : 0
  const color     = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444'
  const hasPending = goal.pending_goal_update && goal.pending_goal_update.length > 0

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => navigate('/goals')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'transparent',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {goal.employee_name}
          </h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{goal.review_period}</p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {isManager && !editing && (
            <button onClick={() => setEditing(true)} style={{
              padding: '6px 14px', borderRadius: 8, fontSize: 12.5, fontWeight: 500,
              border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-secondary)', cursor: 'pointer',
            }}>Edit Goals</button>
          )}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color }}>
              {done}/{total}
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>completed</div>
          </div>
        </div>
      </div>

      {/* Progress */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: '16px 20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)' }}>Progress</span>
          <span style={{ fontSize: 13, fontWeight: 600, color }}>{pct}%</span>
        </div>
        <div style={{ height: 8, background: 'var(--color-border)', borderRadius: 4 }}>
          <div style={{ height: '100%', borderRadius: 4, width: `${pct}%`, background: color, transition: 'width 0.4s ease' }} />
        </div>
        {goal.approved_by && (
          <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 8 }}>
            ✓ Approved by {goal.approved_by} · {goal.approved_at ? new Date(goal.approved_at).toLocaleDateString() : ''}
          </div>
        )}
      </div>

      {/* Pending approval banner */}
      {hasPending && isManager && (
        <div style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 'var(--radius-lg)', padding: '16px 20px',
        }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#F59E0B', marginBottom: 10 }}>
            ⚠ Goal update pending your approval
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }}>
            {goal.pending_goal_update.map((g, i) => (
              <div key={i} style={{ fontSize: 13, color: 'var(--color-text-primary)' }}>• {g}</div>
            ))}
          </div>
          <textarea
            value={comments}
            onChange={e => setComments(e.target.value)}
            placeholder="Add manager comments (optional)…"
            rows={2}
            style={{
              width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
              border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-primary)', resize: 'vertical', outline: 'none',
              boxSizing: 'border-box', marginBottom: 12, fontFamily: 'inherit',
            }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleApprove} disabled={approving} style={{
              padding: '7px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              border: 'none', background: '#10B981', color: '#fff',
              cursor: approving ? 'not-allowed' : 'pointer', opacity: approving ? 0.6 : 1,
            }}>✓ Approve</button>
            <button onClick={handleReject} disabled={approving} style={{
              padding: '7px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)',
              color: '#EF4444', cursor: approving ? 'not-allowed' : 'pointer', opacity: approving ? 0.6 : 1,
            }}>✕ Reject</button>
          </div>
        </div>
      )}

      {/* Goals list / edit */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--color-border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)' }}>
            Goals {editing && <span style={{ fontSize: 12, color: '#6366F1', fontWeight: 400 }}>(editing)</span>}
          </span>
        </div>

        {editing ? (
          <div style={{ padding: 20 }}>
            <textarea
              value={editGoals}
              onChange={e => setEditGoals(e.target.value)}
              rows={8}
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13.5,
                border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)', resize: 'vertical', outline: 'none',
                boxSizing: 'border-box', fontFamily: 'inherit', lineHeight: 1.6,
              }}
              placeholder="One goal per line…"
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
              <button onClick={() => setEditing(false)} style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: '1px solid var(--color-border)', background: 'transparent',
                color: 'var(--color-text-secondary)', cursor: 'pointer',
              }}>Cancel</button>
              <button onClick={handleSaveEdit} disabled={saving} style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: 'none', background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
                color: '#fff', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
              }}>{saving ? 'Saving…' : 'Save & Submit for Approval'}</button>
            </div>
          </div>
        ) : (
          <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {goalsList.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--color-text-muted)', padding: '12px 0' }}>No goals set yet.</div>
            ) : goalsList.map((g, i) => {
              const isDone = achieved.includes(g)
              return (
                <div key={i} style={{
                  display: 'flex', gap: 12, alignItems: 'flex-start',
                  padding: '8px 0', borderBottom: i < goalsList.length - 1 ? '1px solid var(--color-border)' : 'none',
                }}>
                  <span style={{
                    width: 20, height: 20, borderRadius: '50%', flexShrink: 0, marginTop: 1,
                    background: isDone ? 'rgba(16,185,129,0.15)' : 'var(--color-bg-elevated)',
                    border: `1.5px solid ${isDone ? '#10B981' : 'var(--color-border)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, color: '#10B981',
                  }}>{isDone ? '✓' : ''}</span>
                  <span style={{
                    fontSize: 13.5, color: isDone ? 'var(--color-text-secondary)' : 'var(--color-text-primary)',
                    textDecoration: isDone ? 'line-through' : 'none',
                    opacity: isDone ? 0.6 : 1, lineHeight: 1.5, paddingTop: 1,
                  }}>{typeof g === 'string' ? g : g.goal || JSON.stringify(g)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Manager comments */}
      {goal.manager_comments && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 14 }}>
            Manager Comments
          </div>
          <div style={{ padding: '16px 20px', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
            {goal.manager_comments}
          </div>
        </div>
      )}
    </div>
  )
}