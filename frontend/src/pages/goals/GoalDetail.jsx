import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { goalsApi } from '../../api/goals'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

export default function GoalDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [goal, setGoal]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    goalsApi.getOne(id)
      .then(setGoal)
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <PageLoader />
  if (!goal) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Goal not found</div>

  const rating = goal.overall_rating || 0
  const scale  = goal.rating_scale || 5
  const pct    = scale > 0 ? Math.round((rating / scale) * 100) : 0

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => navigate('/goals')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer',
        }}>← Back</button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>{goal.employee_name}</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{goal.review_period}</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: pct >= 80 ? 'var(--color-success-text)' : pct >= 50 ? 'var(--color-warning-text)' : 'var(--color-danger-text)' }}>
            {rating}/{scale}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Overall Rating</div>
        </div>
      </div>

      {/* Rating bar */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: '16px 20px', boxShadow: 'var(--shadow-sm)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>Performance Score</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{pct}%</span>
        </div>
        <div style={{ height: 8, background: 'var(--color-border)', borderRadius: 4 }}>
          <div style={{
            height: '100%', borderRadius: 4,
            width: `${pct}%`,
            background: pct >= 80 ? 'var(--color-success-text)' : pct >= 50 ? 'var(--color-warning-text)' : 'var(--color-danger-text)',
            transition: 'width 0.4s ease',
          }} />
        </div>
      </div>

      {/* Goals list */}
      {goal.goals?.length > 0 && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden', boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 14 }}>Goals</div>
          <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {goal.goals.map((g, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '8px 0', borderBottom: i < goal.goals.length - 1 ? '1px solid var(--color-border)' : 'none' }}>
                <div style={{
                  width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                  background: 'var(--color-primary-light)', color: 'var(--color-primary)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600,
                }}>{i + 1}</div>
                <span style={{ fontSize: 13.5, color: 'var(--color-text-primary)', lineHeight: 1.5, paddingTop: 2 }}>
                  {typeof g === 'string' ? g : g.goal || JSON.stringify(g)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manager feedback */}
      {goal.manager_feedback && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden', boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 14 }}>Manager Feedback</div>
          <div style={{ padding: '16px 20px', fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
            {goal.manager_feedback}
          </div>
        </div>
      )}
    </div>
  )
}