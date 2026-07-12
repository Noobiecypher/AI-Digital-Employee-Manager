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
  const isManager = ['manager', 'admin', 'hr'].includes(user?.role)
  const isEmployee = user?.role === 'employee'

  const [goal, setGoal]             = useState(null)
  const [loading, setLoading]       = useState(true)
  const [editing, setEditing]       = useState(false)
  const [editGoals, setEditGoals]   = useState('')
  const [saving, setSaving]         = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [reviewing, setReviewing]   = useState(false)
  const [comments, setComments]     = useState('')
  // Local achieved state for employee ticking
  const [localAchieved, setLocalAchieved] = useState([])

  const load = () => {
    setLoading(true)
    goalsApi.getOne(decodeURIComponent(employee_name), decodeURIComponent(period))
      .then(data => {
        setGoal(data)
        setEditGoals((data.goals_set || []).join('\n'))
        setLocalAchieved(data.goals_achieved || [])
      })
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [employee_name, period])

  // Manager: save edited goals list + optional deadline
  const handleSaveGoals = async () => {
    setSaving(true)
    try {
      const newGoals = editGoals.split('\n').map(s => s.trim()).filter(Boolean)
      await goalsApi.update(
        decodeURIComponent(employee_name),
        decodeURIComponent(period),
        { goals_set: newGoals }
      )
      toast.success('Goals updated')
      setEditing(false)
      load()
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setSaving(false)
    }
  }

  // Employee: toggle a goal tick
  const toggleGoal = (g) => {
    setLocalAchieved(prev =>
      prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]
    )
  }

  // Employee: submit ticked goals for manager review
  const handleSubmitForReview = async () => {
    setSubmitting(true)
    try {
      await goalsApi.requestUpdate(
        decodeURIComponent(employee_name),
        decodeURIComponent(period),
        localAchieved
      )
      toast.success('Submitted', 'Your progress has been sent to your manager for review')
      load()
    } catch (err) {
      toast.error('Submit failed', err.message)
    } finally {
      setSubmitting(false)
    }
  }

  // Manager: approve or reject
  const handleReview = async (decision) => {
    setReviewing(true)
    try {
      await goalsApi.review(
        decodeURIComponent(employee_name),
        decodeURIComponent(period),
        decision,
        comments || null
      )
      toast.success(decision === 'approved' ? 'Goals approved' : 'Goals rejected',
        decision === 'approved' ? 'Employee goals have been approved' : 'Sent back to employee')
      setComments('')
      load()
    } catch (err) {
      toast.error('Review failed', err.message)
    } finally {
      setReviewing(false)
    }
  }

  if (loading) return <PageLoader />
  if (!goal) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
      Goal not found
    </div>
  )

  const goalsList  = goal.goals_set || []
  const achieved   = goal.goals_achieved || []
  const total      = goalsList.length
  const done       = achieved.length
  const pct        = total > 0 ? Math.round((done / total) * 100) : 0
  const color      = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444'
  const hasPending = goal.status === 'pending_approval' ||
    (goal.pending_goal_update && Object.keys(goal.pending_goal_update).length > 0)
  const allDone    = goalsList.length > 0 && localAchieved.length === goalsList.length
  const isDirty    = JSON.stringify([...localAchieved].sort()) !== JSON.stringify([...achieved].sort())

  // Deadline display
  const deadlineStr = goal.deadline
    ? new Date(goal.deadline).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : null
  const deadlinePast = goal.deadline && new Date(goal.deadline) < new Date()

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Header */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => navigate(-1)} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'transparent',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {goal.employee_name}
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{goal.review_period}</span>
            {deadlineStr && (
              <span style={{
                fontSize: 11.5, fontWeight: 500, padding: '1px 8px', borderRadius: 10,
                background: deadlinePast ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                color: deadlinePast ? '#EF4444' : '#F59E0B',
                border: `1px solid ${deadlinePast ? 'rgba(239,68,68,0.25)' : 'rgba(245,158,11,0.25)'}`,
              }}>
                {deadlinePast ? '⚠ Overdue' : '📅'} {deadlineStr}
              </span>
            )}
          </div>
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
            <div style={{ fontSize: 22, fontWeight: 700, color }}>{done}/{total}</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>completed</div>
          </div>
        </div>
      </div>

      {/* Progress bar */}
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
          <div style={{ fontSize: 11.5, color: '#10B981', marginTop: 8 }}>
            ✓ Approved by {goal.approved_by}
            {goal.approved_at ? ` · ${new Date(goal.approved_at).toLocaleDateString()}` : ''}
          </div>
        )}
      </div>

      {/* Pending approval banner — show to manager */}
      {hasPending && isManager && (
        <div style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 'var(--radius-lg)', padding: '16px 20px',
        }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#F59E0B', marginBottom: 8 }}>
            ⚠ Employee submitted goals for your review
          </div>
          {goal.pending_goal_update?.goals_achieved && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                Marked as achieved:
              </div>
              {goal.pending_goal_update.goals_achieved.map((g, i) => (
                <div key={i} style={{ fontSize: 13, color: 'var(--color-text-primary)', padding: '3px 0' }}>
                  ✓ {g}
                </div>
              ))}
            </div>
          )}
          <textarea
            value={comments}
            onChange={e => setComments(e.target.value)}
            placeholder="Add feedback or comments (optional)…"
            rows={2}
            style={{
              width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
              border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-primary)', resize: 'vertical', outline: 'none',
              boxSizing: 'border-box', marginBottom: 12, fontFamily: 'inherit',
            }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => handleReview('approved')} disabled={reviewing} style={{
              padding: '7px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              border: 'none', background: '#10B981', color: '#fff',
              cursor: reviewing ? 'not-allowed' : 'pointer', opacity: reviewing ? 0.6 : 1,
            }}>✓ Approve</button>
            <button onClick={() => handleReview('rejected')} disabled={reviewing} style={{
              padding: '7px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)',
              color: '#EF4444', cursor: reviewing ? 'not-allowed' : 'pointer', opacity: reviewing ? 0.6 : 1,
            }}>✕ Reject</button>
          </div>
        </div>
      )}

      {/* Goals list */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid var(--color-border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)' }}>
            Goals
            {editing && <span style={{ fontSize: 12, color: '#6366F1', fontWeight: 400, marginLeft: 8 }}>(editing)</span>}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{total} goal{total !== 1 ? 's' : ''}</span>
        </div>

        {editing ? (
          <div style={{ padding: 20 }}>
            <p style={{ fontSize: 12.5, color: 'var(--color-text-muted)', marginBottom: 10 }}>
              One goal per line.
            </p>
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
              <button onClick={() => { setEditing(false); setEditGoals((goal.goals_set || []).join('\n')) }} style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: '1px solid var(--color-border)', background: 'transparent',
                color: 'var(--color-text-secondary)', cursor: 'pointer',
              }}>Cancel</button>
              <button onClick={handleSaveGoals} disabled={saving} style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: 'none', background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
                color: '#fff', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
              }}>
                {saving ? 'Saving…' : 'Save Goals'}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {goalsList.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--color-text-muted)', padding: '12px 0' }}>
                No goals set yet.
              </div>
            ) : goalsList.map((g, i) => {
              const isDone = isEmployee ? localAchieved.includes(g) : achieved.includes(g)
              return (
                <div
                  key={i}
                  onClick={() => isEmployee && toggleGoal(g)}
                  style={{
                    display: 'flex', gap: 12, alignItems: 'flex-start', padding: '10px 0',
                    borderBottom: i < goalsList.length - 1 ? '1px solid var(--color-border)' : 'none',
                    cursor: isEmployee ? 'pointer' : 'default',
                  }}
                >
                  <span style={{
                    width: 22, height: 22, borderRadius: 6, flexShrink: 0, marginTop: 1,
                    background: isDone ? '#10B981' : 'var(--color-bg-elevated)',
                    border: `2px solid ${isDone ? '#10B981' : 'var(--color-border)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, color: '#fff', transition: 'all 0.15s',
                  }}>{isDone ? '✓' : ''}</span>
                  <span style={{
                    fontSize: 13.5, lineHeight: 1.5, paddingTop: 2, flex: 1,
                    color: isDone ? 'var(--color-text-secondary)' : 'var(--color-text-primary)',
                    textDecoration: isDone ? 'line-through' : 'none',
                    opacity: isDone ? 0.6 : 1,
                  }}>
                    {typeof g === 'string' ? g : g.goal || JSON.stringify(g)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Employee: submit for review */}
      {isEmployee && !editing && goalsList.length > 0 && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '16px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-text-primary)' }}>
              {allDone ? '🎉 All goals completed!' : `${localAchieved.length} of ${goalsList.length} goals marked done`}
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
              {isDirty ? 'You have unsaved changes — submit to send for manager review' : 'Tick goals above to mark them complete'}
            </div>
          </div>
          <button
            onClick={handleSubmitForReview}
            disabled={submitting || !isDirty}
            style={{
              padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              border: 'none',
              background: isDirty ? 'linear-gradient(135deg, #6366F1, #4F46E5)' : 'rgba(255,255,255,0.08)',
              color: isDirty ? '#fff' : 'var(--color-text-muted)',
              cursor: isDirty && !submitting ? 'pointer' : 'not-allowed',
              opacity: submitting ? 0.7 : 1,
              boxShadow: isDirty ? '0 0 16px rgba(99,102,241,0.25)' : 'none',
              minWidth: 160,
            }}
          >
            {submitting ? 'Submitting…' : '→ Submit for Review'}
          </button>
        </div>
      )}

      {/* Manager comments */}
      {goal.manager_comments && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)' }}>
            Manager Feedback
          </div>
          <div style={{ padding: '16px 20px', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
            {goal.manager_comments}
          </div>
        </div>
      )}
    </div>
  )
}