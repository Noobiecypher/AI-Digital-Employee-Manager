import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { goalsApi } from '../../api/goals'
import { employeesApi } from '../../api/employees'
import { useToast } from '../../components/layout/AppLayout'

const REVIEW_PERIODS = [
  'Q1 2026', 'Q2 2026', 'Q3 2026', 'Q4 2026',
  'Q1 2027', 'Q2 2027', 'Q3 2027', 'Q4 2027',
]

const labelStyle = {
  fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)',
  display: 'block', marginBottom: 7, letterSpacing: '0.03em', textTransform: 'uppercase',
}

const inputStyle = {
  width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13.5,
  border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
  color: 'var(--color-text-primary)', outline: 'none', boxSizing: 'border-box',
}

export default function GoalForm() {
  const navigate = useNavigate()
  const toast = useToast()

  const [employees, setEmployees] = useState([])
  const [loading, setLoading]     = useState(false)

  const [employeeName, setEmployeeName] = useState('')
  const [reviewPeriod, setReviewPeriod] = useState('')
  const [goalsText, setGoalsText]       = useState('')
  const [deadline, setDeadline]         = useState('')

  useEffect(() => {
    employeesApi.getAll()
      .then(res => {
        const arr = Array.isArray(res) ? res : res?.items || res?.employees || []
        setEmployees(arr)
      })
      .catch(() => {})
  }, [])

  const handleSubmit = async () => {
    if (!employeeName || !reviewPeriod || !goalsText.trim()) {
      toast.warning('Required', 'Fill in employee, period, and at least one goal')
      return
    }

    const goals_set = goalsText.split('\n').map(s => s.trim()).filter(Boolean)

    setLoading(true)
    try {
      await goalsApi.create({
        employee_name: employeeName,
        review_period: reviewPeriod,
        goals_set,
        goals_achieved: [],
        ...(deadline ? { deadline } : {}),
      })
      toast.success('Goals assigned', `Goals set for ${employeeName}`)
      navigate('/goals')
    } catch (err) {
      toast.error('Failed to create', err.message)
    } finally {
      setLoading(false)
    }
  }

  const goals_set = goalsText.split('\n').map(s => s.trim()).filter(Boolean)

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/goals')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'transparent',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
          Assign Goals
        </h2>
      </div>

      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)', padding: '28px 32px',
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>

        {/* Employee */}
        <div>
          <label style={labelStyle}>Employee *</label>
          <select value={employeeName} onChange={e => setEmployeeName(e.target.value)} style={inputStyle}>
            <option value="">Select employee...</option>
            {employees.map(emp => (
              <option key={emp.employee_id || emp.employee_name} value={emp.employee_name}>
                {emp.employee_name} {emp.role ? `— ${emp.role}` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Review period + Deadline side by side */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <label style={labelStyle}>Review Period *</label>
            <select value={reviewPeriod} onChange={e => setReviewPeriod(e.target.value)} style={inputStyle}>
              <option value="">Select period...</option>
              {REVIEW_PERIODS.map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Deadline <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(optional)</span></label>
            <input
              type="date"
              value={deadline}
              onChange={e => setDeadline(e.target.value)}
              min={new Date().toISOString().split('T')[0]}
              style={inputStyle}
            />
          </div>
        </div>

        {/* Goals */}
        <div>
          <label style={labelStyle}>
            Goals * <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(one per line)</span>
          </label>
          <textarea
            value={goalsText}
            onChange={e => setGoalsText(e.target.value)}
            placeholder={'Complete API redesign\nReduce bug count by 20%\nWrite unit tests for core modules'}
            rows={6}
            style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.7, fontFamily: 'inherit' }}
          />
          {goals_set.length > 0 && (
            <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 5 }}>
              {goals_set.length} goal{goals_set.length !== 1 ? 's' : ''} entered
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
          <button onClick={() => navigate('/goals')} style={{
            padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: '1px solid var(--color-border)', background: 'transparent',
            color: 'var(--color-text-secondary)', cursor: 'pointer',
          }}>Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            style={{
              padding: '9px 24px', borderRadius: 8, fontSize: 13, fontWeight: 600,
              border: 'none', background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
              color: '#fff', cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              boxShadow: '0 0 16px rgba(99,102,241,0.25)',
            }}
          >
            {loading ? 'Assigning...' : 'Assign Goals'}
          </button>
        </div>
      </div>
    </div>
  )
}