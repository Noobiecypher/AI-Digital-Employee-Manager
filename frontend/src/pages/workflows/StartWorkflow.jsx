import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { workflowsApi } from '../../api/workflows'
import { documentsApi } from '../../api/documents'
import { useToast } from '../../components/layout/AppLayout'
import { WORKFLOW_TYPES } from '../../constants/workflowStates'

const WF_DESCRIPTIONS = {
  hire_employee:      'Full recruitment pipeline with candidate shortlisting and offer generation',
  onboard_employee:   'Generate onboarding plan and assign tasks for a new hire',
  sales_outreach:     'Lead research, outreach strategy, and email content generation',
  market_research:    'Market analysis, competitor research, and summary report',
  performance_review: 'Collect employee data and generate performance review',
  performance_report: 'Generate a performance report from existing data',
}

// Workflows that need document selectors and their slot config
const DOC_SLOTS = {
  market_research: [
    { slot: 'market_research', label: 'Reference Documents', field: 'document_ids', multi: true, optional: true },
  ],
  performance_report: [
    { slot: 'performance_report.hr',    label: 'HR Documents',    field: 'hr_document_ids',    multi: true, optional: true },
    { slot: 'performance_report.sales', label: 'Sales Documents', field: 'sales_document_ids', multi: true, optional: true },
  ],
}

function DocumentSelector({ slot, label, field, multi, onChange }) {
  const [docs, setDocs]     = useState([])
  const [selected, setSelected] = useState([])
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    documentsApi.getEligible(slot)
      .then(res => setDocs(res?.items || res || []))
      .catch(() => setDocs([]))
      .finally(() => setLoading(false))
  }, [slot])

  const toggle = (id) => {
    const next = selected.includes(id)
      ? selected.filter(x => x !== id)
      : multi ? [...selected, id] : [id]
    setSelected(next)
    onChange(next)
  }

  if (loading) return (
    <div style={{ fontSize: 12.5, color: 'var(--color-text-muted)', padding: '8px 0' }}>
      Loading eligible documents…
    </div>
  )

  return (
    <div>
      <label style={labelStyle}>
        {label}
        <span style={{ fontWeight: 400, color: 'var(--color-text-muted)', marginLeft: 6 }}>(optional)</span>
      </label>
      {docs.length === 0 ? (
        <div style={{
          padding: '12px 14px', borderRadius: 8, fontSize: 12.5,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          color: 'var(--color-text-muted)',
        }}>
          No eligible documents found for this slot.{' '}
          <span
            onClick={() => window.open('/documents/upload', '_blank')}
            style={{ color: '#818CF8', cursor: 'pointer', textDecoration: 'underline' }}
          >Upload one</span>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {docs.map(doc => {
            const isSelected = selected.includes(doc.document_id)
            return (
              <div
                key={doc.document_id}
                onClick={() => toggle(doc.document_id)}
                style={{
                  padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                  border: `1.5px solid ${isSelected ? '#6366F1' : 'var(--color-border)'}`,
                  background: isSelected ? 'rgba(99,102,241,0.1)' : 'var(--color-bg-elevated)',
                  display: 'flex', alignItems: 'center', gap: 10,
                  transition: 'all 0.12s',
                }}
              >
                <span style={{
                  width: 16, height: 16, borderRadius: multi ? 4 : '50%', flexShrink: 0,
                  border: `1.5px solid ${isSelected ? '#6366F1' : 'var(--color-text-muted)'}`,
                  background: isSelected ? '#6366F1' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, color: '#fff',
                }}>{isSelected ? '✓' : ''}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: isSelected ? '#818CF8' : 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {doc.original_filename || doc.document_id}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 1 }}>
                    {doc.document_type?.replace(/_/g, ' ')} · {doc.status}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
      {selected.length > 0 && (
        <div style={{ fontSize: 11.5, color: '#818CF8', marginTop: 6 }}>
          {selected.length} document{selected.length !== 1 ? 's' : ''} selected
        </div>
      )}
    </div>
  )
}

export default function StartWorkflow() {
  const navigate = useNavigate()
  const toast    = useToast()

  const [selected, setSelected]     = useState('')
  const [context, setContext]       = useState('')
  const [loading, setLoading]       = useState(false)
  const [contextError, setContextError] = useState('')
  // document slot selections: { document_ids: [], hr_document_ids: [], sales_document_ids: [] }
  const [docSelections, setDocSelections] = useState({})

  const handleDocChange = (field, ids) => {
    setDocSelections(prev => ({ ...prev, [field]: ids }))
  }

  const handleWorkflowSelect = (value) => {
    setSelected(value)
    setDocSelections({}) // reset doc selections on workflow type change
  }

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

    // Merge document selections into params (only non-empty arrays)
    const docParams = {}
    Object.entries(docSelections).forEach(([field, ids]) => {
      if (ids && ids.length > 0) docParams[field] = ids
    })

    setLoading(true)
    try {
      const payload = {
        objective_id: selected,
        params: { ...parsedContext, ...docParams },
      }
      const res = await workflowsApi.start(payload)
      const id = res.workflow_id || res._id || res.id
      toast.success('Workflow started', `ID: ${id}`)
      navigate(id ? `/workflows/${id}` : '/workflows')
    } catch (err) {
      const msg = typeof err?.message === 'string' ? err.message
        : typeof err === 'string' ? err : JSON.stringify(err)
      toast.error('Failed to start', msg)
    } finally {
      setLoading(false)
    }
  }

  const slots = DOC_SLOTS[selected] || []

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
          <label style={{ ...labelStyle, marginBottom: 12 }}>Workflow Type *</label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 10 }}>
            {WORKFLOW_TYPES.map(wf => (
              <div
                key={wf.value}
                onClick={() => handleWorkflowSelect(wf.value)}
                style={{
                  padding: '14px 16px', borderRadius: 10,
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

        {/* Document selectors — only for market_research and performance_report */}
        {slots.length > 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 18,
            padding: '20px', borderRadius: 10,
            background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.15)',
          }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: '#818CF8', letterSpacing: '0.02em' }}>
              📎 Attach Documents (optional)
            </div>
            {slots.map(s => (
              <DocumentSelector
                key={s.slot}
                slot={s.slot}
                label={s.label}
                field={s.field}
                multi={s.multi}
                onChange={(ids) => handleDocChange(s.field, ids)}
              />
            ))}
          </div>
        )}

        {/* Additional context JSON */}
        <div>
          <label style={{ ...labelStyle, marginBottom: 6 }}>
            Additional Context{' '}
            <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>(optional JSON)</span>
          </label>
          <textarea
            value={context}
            onChange={e => { setContext(e.target.value); setContextError('') }}
            placeholder={'{\n  "role": "Backend Engineer",\n  "department": "Engineering"\n}'}
            rows={5}
            style={{
              width: '100%', padding: '10px 12px', borderRadius: 8,
              border: `1px solid ${contextError ? '#EF4444' : 'var(--color-border)'}`,
              background: 'var(--color-bg-elevated)', color: 'var(--color-text-primary)',
              fontSize: 12.5, fontFamily: 'ui-monospace, monospace',
              resize: 'vertical', outline: 'none', boxSizing: 'border-box', lineHeight: 1.6,
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
              border: 'none',
              background: selected ? 'linear-gradient(135deg, #6366F1, #4F46E5)' : 'rgba(255,255,255,0.1)',
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

const labelStyle = {
  fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-secondary)',
  letterSpacing: '0.02em', display: 'block',
}