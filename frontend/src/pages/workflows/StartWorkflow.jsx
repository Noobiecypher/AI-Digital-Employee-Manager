import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { workflowsApi } from '../../api/workflows'
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

// Mirrors the *Params models in backend/models.py.
// type: 'text' | 'number' | 'list' | 'textarea'
// 'list' fields are entered as comma-separated text and split into an array on submit.
const WORKFLOW_PARAMS_CONFIG = {
  hire_employee: [
    { name: 'role',             label: 'Role',              type: 'text',    required: true },
    { name: 'department',       label: 'Department',        type: 'text',    required: true },
    { name: 'job_type',         label: 'Job Type',          type: 'text',    required: true, placeholder: 'full-time, contract, etc.' },
    { name: 'experience_years', label: 'Experience (years)', type: 'number', required: false, default: 0 },
    { name: 'skills_required',  label: 'Skills Required',   type: 'list',    required: false, placeholder: 'Python, FastAPI, MongoDB' },
    { name: 'location',         label: 'Location',          type: 'text',    required: false },
    { name: 'salary_range',     label: 'Salary Range',      type: 'text',    required: false },
  ],
  onboard_employee: [
    { name: 'employee_name', label: 'Employee Name', type: 'text', required: true },
    { name: 'role',          label: 'Role',          type: 'text', required: false },
    { name: 'department',    label: 'Department',    type: 'text', required: false },
    { name: 'joining_date',  label: 'Joining Date',  type: 'text', required: false, placeholder: 'YYYY-MM-DD' },
    { name: 'manager_name',  label: 'Manager Name',  type: 'text', required: false },
    { name: 'work_mode',     label: 'Work Mode',     type: 'text', required: false, placeholder: 'remote, hybrid, onsite' },
  ],
  sales_outreach: [
    { name: 'target_segment',    label: 'Target Segment',     type: 'text', required: true },
    { name: 'outreach_channels', label: 'Outreach Channels',  type: 'list', required: true, placeholder: 'email, linkedin, call' },
    { name: 'campaign_goal',     label: 'Campaign Goal',      type: 'text', required: true },
    { name: 'product_name',      label: 'Product Name',       type: 'text', required: false },
    { name: 'pain_points',       label: 'Pain Points',        type: 'list', required: false, placeholder: 'slow onboarding, high cost' },
  ],
  performance_report: [
    { name: 'report_period',       label: 'Report Period',        type: 'text', required: true, placeholder: 'Q2 2026' },
    { name: 'departments',         label: 'Departments',          type: 'list', required: true, placeholder: 'Engineering, Sales' },
    { name: 'metrics_to_include',  label: 'Metrics to Include',   type: 'list', required: true, placeholder: 'revenue, deals_won' },
    { name: 'report_type',         label: 'Report Type',          type: 'text', required: true },
  ],
  performance_review: [
    { name: 'employee_name',    label: 'Employee Name',    type: 'text',     required: true },
    { name: 'review_period',    label: 'Review Period',    type: 'text',     required: true, placeholder: 'H1 2026' },
    { name: 'manager_comments', label: 'Manager Comments', type: 'textarea', required: true },
    { name: 'role',             label: 'Role',             type: 'text',     required: false },
    { name: 'department',       label: 'Department',       type: 'text',     required: false },
    { name: 'goals_set',        label: 'Goals Set',        type: 'list',     required: false, placeholder: 'Ship feature X, mentor junior dev' },
    { name: 'goals_achieved',   label: 'Goals Achieved',   type: 'list',     required: false },
    { name: 'rating_scale',     label: 'Rating Scale',     type: 'number',   required: false, default: 5 },
  ],
  market_research: [
    { name: 'research_topic', label: 'Research Topic', type: 'text', required: true },
    { name: 'competitors',    label: 'Competitors',    type: 'list', required: true, placeholder: 'Acme Inc, Globex Corp' },
    { name: 'focus_areas',    label: 'Focus Areas',    type: 'list', required: true, placeholder: 'pricing, market share' },
    { name: 'output_format',  label: 'Output Format',  type: 'text', required: true, placeholder: 'pdf, slide deck, summary' },
  ],
}

const inputStyle = {
  width: '100%', padding: '9px 12px', borderRadius: 8,
  border: '1px solid var(--color-border)',
  background: 'var(--color-bg-elevated)',
  color: 'var(--color-text-primary)',
  fontSize: 13, outline: 'none', boxSizing: 'border-box',
}

function FormField({ field, value, onChange, error }) {
  const commonProps = {
    value: value ?? '',
    onChange: e => onChange(field.name, e.target.value),
    placeholder: field.placeholder || '',
    style: { ...inputStyle, border: `1px solid ${error ? '#EF4444' : 'var(--color-border)'}` },
  }

  return (
    <div>
      <label style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--color-text-secondary)', display: 'block', marginBottom: 5 }}>
        {field.label}{field.required && <span style={{ color: '#EF4444' }}> *</span>}
        {field.type === 'list' && (
          <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}> (comma-separated)</span>
        )}
      </label>
      {field.type === 'textarea' ? (
        <textarea rows={3} {...commonProps} />
      ) : field.type === 'number' ? (
        <input type="number" {...commonProps} />
      ) : (
        <input type="text" {...commonProps} />
      )}
      {error && <div style={{ fontSize: 11.5, color: '#EF4444', marginTop: 4 }}>{error}</div>}
    </div>
  )
}

export default function StartWorkflow() {
  const navigate  = useNavigate()
  const toast     = useToast()
  const [selected, setSelected] = useState('')
  const [values, setValues]     = useState({})
  const [errors, setErrors]     = useState({})
  const [loading, setLoading]   = useState(false)

  // Reset field values whenever the workflow type changes
  useEffect(() => {
    setValues({})
    setErrors({})
  }, [selected])

  const fields = WORKFLOW_PARAMS_CONFIG[selected] || []

  const handleFieldChange = (name, value) => {
    setValues(v => ({ ...v, [name]: value }))
    if (errors[name]) setErrors(e => ({ ...e, [name]: null }))
  }

  const buildParams = () => {
    const params = {}
    for (const field of fields) {
      const raw = values[field.name]
      if (field.type === 'list') {
        const arr = (raw || '').split(',').map(s => s.trim()).filter(Boolean)
        if (arr.length) params[field.name] = arr
      } else if (field.type === 'number') {
        if (raw !== undefined && raw !== '') params[field.name] = Number(raw)
      } else {
        if (raw) params[field.name] = raw
      }
    }
    return params
  }

  const validate = () => {
    const newErrors = {}
    for (const field of fields) {
      if (!field.required) continue
      const raw = values[field.name]
      const empty = field.type === 'list'
        ? !(raw || '').split(',').map(s => s.trim()).filter(Boolean).length
        : !raw
      if (empty) newErrors[field.name] = 'Required'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async () => {
    if (!selected) return toast.warning('Required', 'Select a workflow type')
    if (!validate()) return toast.warning('Missing fields', 'Fill in all required fields')

    setLoading(true)
    try {
      const payload = { objective_id: selected, params: buildParams() }
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

        {/* Dynamic params form */}
        {selected && (
          <div>
            <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-secondary)', letterSpacing: '0.02em', display: 'block', marginBottom: 12 }}>
              Workflow Details
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14 }}>
              {fields.map(field => (
                <div key={field.name} style={field.type === 'textarea' ? { gridColumn: '1 / -1' } : undefined}>
                  <FormField
                    field={field}
                    value={values[field.name]}
                    onChange={handleFieldChange}
                    error={errors[field.name]}
                  />
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 10 }}>
              Fields marked * are required. Everything else is optional and will use backend defaults if left blank.
            </div>
          </div>
        )}

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