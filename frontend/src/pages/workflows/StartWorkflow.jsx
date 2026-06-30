import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { workflowsApi } from '../../api/workflows'
import { useToast } from '../../components/layout/AppLayout'
import { WORKFLOW_TYPES } from '../../constants/workflowStates'
import { FormCard, Field, Textarea, FormActions } from '../_shared/FormComponents'

const WF_DESCRIPTIONS = {
  hire_employee:      'Full recruitment pipeline with candidate shortlisting and offer generation',
  onboard_employee:   'Generate onboarding plan and assign tasks for a new hire',
  sales_outreach:     'Lead research, outreach strategy, and email content generation',
  market_research:    'Market analysis, competitor research, and summary report',
  performance_review: 'Collect employee data and generate performance review',
  performance_report: 'Generate a performance report from existing data',
}

export default function StartWorkflow() {
  const navigate  = useNavigate()
  const toast     = useToast()
  const [selected, setSelected] = useState('')
  const [context, setContext]   = useState('')
  const [loading, setLoading]   = useState(false)
  const [contextError, setContextError] = useState('')

  const handleSubmit = async () => {
    if (!selected) return toast.warning('Required', 'Select a workflow type')

    let parsedContext = {}
    if (context.trim()) {
      try {
        parsedContext = JSON.parse(context)
        setContextError('')
      } catch {
        setContextError('Invalid JSON — check your syntax')
        return
      }
    }

    setLoading(true)
    try {
      // Real API expects: { objective_id, ...context }
      const payload = { objective_id: selected, ...parsedContext }
      const res = await workflowsApi.start(payload)
      const id = res.workflow_id || res._id || res.id
      toast.success('Workflow started', `ID: ${id}`)
      navigate(id ? `/workflows/${id}` : '/workflows')
    } catch (err) {
      toast.error('Failed to start', err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 740, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/workflows')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Start Workflow</h2>
      </div>

      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)', padding: '28px 32px',
        display: 'flex', flexDirection: 'column', gap: 24,
      }}>
        {/* Workflow type selection */}
        <div>
          <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-secondary)', letterSpacing: '0.02em', display: 'block', marginBottom: 12 }}>
            Workflow Type *
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 10 }}>
            {WORKFLOW_TYPES.map(wf => (
              <div
                key={wf.value}
                onClick={() => setSelected(wf.value)}
                style={{
                  padding: '14px 16px',
                  borderRadius: 10,
                  border: `2px solid ${selected === wf.value ? '#6366F1' : 'var(--color-border)'}`,
                  background: selected === wf.value ? 'rgba(99,102,241,0.12)' : 'var(--color-bg-elevated)',
                  cursor: 'pointer', transition: 'all 0.15s',
                  position: 'relative', overflow: 'hidden',
                }}
              >
                {selected === wf.value && (
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: 'linear-gradient(90deg, #6366F1, #06B6D4)' }} />
                )}
                <div style={{ fontSize: 13.5, fontWeight: 600, color: selected === wf.value ? '#818CF8' : 'var(--color-text-primary)', marginBottom: 4 }}>
                  {wf.label}
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
                  {WF_DESCRIPTIONS[wf.value] || ''}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Context JSON */}
        <div>
          <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-secondary)', letterSpacing: '0.02em', display: 'block', marginBottom: 6 }}>
            Additional Context <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>(optional JSON)</span>
          </label>
          <textarea
            value={context}
            onChange={e => { setContext(e.target.value); setContextError('') }}
            placeholder={'{\n  "employee_name": "Alex Sharma",\n  "role": "Backend Engineer"\n}'}
            rows={5}
            style={{
              width: '100%', padding: '10px 12px', borderRadius: 8,
              border: `1px solid ${contextError ? '#EF4444' : 'var(--color-border)'}`,
              background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-primary)',
              fontSize: 12.5, fontFamily: 'ui-monospace, monospace',
              resize: 'vertical', outline: 'none', boxSizing: 'border-box',
              lineHeight: 1.6,
            }}
            onFocus={e => e.target.style.borderColor = contextError ? '#EF4444' : '#6366F1'}
            onBlur={e => e.target.style.borderColor = contextError ? '#EF4444' : 'var(--color-border)'}
          />
          {contextError && <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>{contextError}</div>}
          <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 6 }}>
            Pass extra data to the workflow agent. Leave blank to use defaults.
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
          <button onClick={() => navigate('/workflows')} style={{
            padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
            cursor: 'pointer', color: 'var(--color-text-secondary)',
          }}>Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={loading || !selected}
            style={{
              padding: '9px 24px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              border: 'none', background: selected ? 'linear-gradient(135deg, #6366F1, #4F46E5)' : 'rgba(255,255,255,0.1)',
              color: selected ? '#fff' : 'var(--color-text-muted)',
              cursor: loading || !selected ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              boxShadow: selected ? '0 0 16px rgba(99,102,241,0.25)' : 'none',
              minWidth: 140, transition: 'all 0.15s',
            }}
          >
            {loading ? 'Starting...' : '⚡ Start Workflow'}
          </button>
        </div>
      </div>
    </div>
  )
}