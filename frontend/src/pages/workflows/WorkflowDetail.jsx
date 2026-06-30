import { useParams, useNavigate } from 'react-router-dom'
import { useWorkflowPolling } from '../../hooks/useWorkflowPolling'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import StatusBadge from '../../components/ui/StatusBadge'
import { STATE_META } from '../../constants/workflowStates'
import { useState } from 'react'

function getStatus(wf) {
  if (!wf) return 'pending'
  if (wf.awaiting_human_input) return 'waiting_for_human'
  return wf.status || wf.state || 'pending'
}

export default function WorkflowDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { workflow, loading, error } = useWorkflowPolling(id)

  if (loading) return <PageLoader />
  if (error)    return <ErrorState message={error} onBack={() => navigate('/workflows')} />
  if (!workflow) return <ErrorState message="Workflow not found" onBack={() => navigate('/workflows')} />

  const status    = getStatus(workflow)
  const meta      = STATE_META[status] || { label: status, color: 'default' }
  const isLive    = ['running', 'pending'].includes(status)
  const taskOutputs = Array.isArray(workflow.task_outputs) ? workflow.task_outputs : []
  const type      = workflow.objective_id || workflow.workflow_type || ''
  const result    = workflow.result || null

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => navigate('/workflows')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Workflow'}
          </h2>
          <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2, fontFamily: 'monospace' }}>{id}</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isLive && (
            <span style={{ fontSize: 11, color: '#818CF8', display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'currentColor', display: 'inline-block', animation: 'pulse 1.5s infinite' }} />
              Live
              <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
            </span>
          )}
          <StatusBadge label={meta.label || status} color={meta.color} />
        </div>
      </div>

      {/* Meta info */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: '16px 20px',
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16,
      }}>
        {[
          { label: 'Status',          value: status.replace(/_/g, ' ') },
          { label: 'Approval Status', value: workflow.approval_status || '—' },
          { label: 'Created',         value: workflow.created_at ? new Date(workflow.created_at).toLocaleString() : '—' },
          { label: 'Updated',         value: workflow.updated_at ? new Date(workflow.updated_at).toLocaleString() : '—' },
        ].map(item => (
          <div key={item.label}>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{item.label}</div>
            <div style={{ fontSize: 13, color: 'var(--color-text-primary)', fontWeight: 500, textTransform: 'capitalize' }}>{item.value}</div>
          </div>
        ))}
      </div>

      {/* Approval prompt */}
      {status === 'waiting_for_human' && (
        <div style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 'var(--radius-lg)', padding: '14px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontWeight: 600, color: '#F59E0B', fontSize: 14 }}>⚠️ This workflow is waiting for your approval</span>
          <button onClick={() => navigate('/approvals')} style={{
            padding: '7px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: '#F59E0B', color: '#000', border: 'none', cursor: 'pointer',
          }}>Go to Approvals</button>
        </div>
      )}

      {/* Human feedback */}
      {workflow.human_feedback && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>Human Feedback</div>
          <div style={{ padding: '14px 18px', fontSize: 13.5, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
            {workflow.human_feedback}
          </div>
        </div>
      )}

      {/* Final result */}
      {result && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>Final Result</span>
            <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: 'rgba(245,158,11,0.12)', color: '#F59E0B', fontWeight: 500 }}>
              ⚠ AI-generated
            </span>
          </div>
          <div style={{ padding: '16px 18px' }}>
            {result.executive_summary && (
              <p style={{ fontSize: 13.5, color: 'var(--color-text-secondary)', lineHeight: 1.7, marginBottom: result.system_actions ? 14 : 0 }}>
                {result.executive_summary}
              </p>
            )}
            {result.system_actions?.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                  System Actions
                </div>
                {result.system_actions.map((action, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5 }}>
                    <span style={{ color: '#10B981', fontSize: 14 }}>✓</span>
                    <span style={{ color: 'var(--color-text-primary)' }}>{action}</span>
                  </div>
                ))}
              </div>
            )}
            {!result.executive_summary && !result.system_actions && (
              <pre style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--color-text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, fontFamily: 'inherit' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Task outputs timeline */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', overflow: 'hidden',
      }}>
        <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>Step-by-Step Outputs</span>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {taskOutputs.length} step{taskOutputs.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div style={{ padding: '20px' }}>
          {taskOutputs.length === 0 ? (
            <div style={{ color: 'var(--color-text-muted)', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>
              No task outputs available yet
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {taskOutputs.map((task, i) => (
                <TaskStep key={task.task_id || i} task={task} index={i} isLast={i === taskOutputs.length - 1} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function TaskStep({ task, index, isLast }) {
  const [expanded, setExpanded] = useState(false)

  const renderOutput = (output) => {
    if (!output) return null

    // Job description
    if (output.job_description) return (
      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
        {output.job_description}
      </div>
    )

    // Required skills
    if (output.required_skills) return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {output.required_skills.map(s => (
          <span key={s} style={{ padding: '2px 10px', borderRadius: 10, fontSize: 12, fontWeight: 500, background: 'rgba(99,102,241,0.12)', color: '#818CF8', border: '1px solid rgba(99,102,241,0.2)' }}>{s}</span>
        ))}
      </div>
    )

    // Shortlisted candidates
    if (output.shortlisted_candidates) return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {output.shortlisted_candidates.map((c, i) => (
          <div key={i} style={{ background: 'var(--color-bg-elevated)', borderRadius: 8, padding: '10px 14px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{c.name}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
              {c.experience_years} yrs exp · Match: {Math.round((c.match_score || 0) * 100)}%
            </div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {c.skills?.map(s => (
                <span key={s} style={{ padding: '1px 7px', borderRadius: 10, fontSize: 11, background: 'rgba(16,185,129,0.12)', color: '#10B981', border: '1px solid rgba(16,185,129,0.2)', fontWeight: 500 }}>{s}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    )

    // Interview schedule
    if (output.interview_schedule) return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {output.interview_schedule.map((s, i) => (
          <div key={i} style={{ background: 'var(--color-bg-elevated)', borderRadius: 8, padding: '10px 14px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{s.candidate_name}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 3 }}>
              {s.date} at {s.time} · {s.interviewer}
            </div>
          </div>
        ))}
      </div>
    )

    // Offer details
    if (output.offer_details) return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {output.offer_details.map((o, i) => (
          <div key={i} style={{ background: 'var(--color-bg-elevated)', borderRadius: 8, padding: '10px 14px', border: '1px solid var(--color-border)' }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{o.candidate_name}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 3 }}>
              {o.role} · {o.department} · {o.location}
            </div>
            <div style={{ fontSize: 12, color: '#10B981', marginTop: 3, fontWeight: 600 }}>
              ₹{(o.salary || 0).toLocaleString('en-IN')} per annum
            </div>
          </div>
        ))}
      </div>
    )

    // Approval/feedback outputs
    if (output.approval_status || output.human_feedback) return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {output.approval_status && (
          <div style={{ fontSize: 13 }}>
            <span style={{ color: 'var(--color-text-muted)' }}>Status: </span>
            <span style={{ color: output.approval_status === 'approved' ? '#10B981' : '#F59E0B', fontWeight: 600, textTransform: 'capitalize' }}>
              {output.approval_status}
            </span>
          </div>
        )}
        {output.human_feedback && (
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
            <span style={{ color: 'var(--color-text-muted)' }}>Feedback: </span>
            {output.human_feedback}
          </div>
        )}
        {output.human_input_data && Object.keys(output.human_input_data).length > 0 && (
          <pre style={{ fontSize: 12, color: 'var(--color-text-muted)', background: 'var(--color-bg-elevated)', borderRadius: 6, padding: '8px 10px', margin: 0, whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(output.human_input_data, null, 2)}
          </pre>
        )}
      </div>
    )

    // Fallback — raw JSON
    return (
      <pre style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--color-text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, fontFamily: 'ui-monospace, monospace' }}>
        {JSON.stringify(output, null, 2)}
      </pre>
    )
  }

  return (
    <div style={{ display: 'flex', gap: 14 }}>
      {/* Timeline line + dot */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background: 'rgba(99,102,241,0.15)',
          border: '2px solid #6366F1',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: '#818CF8', flexShrink: 0,
        }}>{index + 1}</div>
        {!isLast && <div style={{ width: 2, flex: 1, background: 'var(--color-border)', minHeight: 16, margin: '4px 0' }} />}
      </div>

      {/* Content */}
      <div style={{ flex: 1, paddingBottom: isLast ? 0 : 16 }}>
        <div
          onClick={() => setExpanded(e => !e)}
          style={{
            background: 'var(--color-bg-surface-2)',
            border: '1px solid var(--color-border)',
            borderRadius: expanded ? '8px 8px 0 0' : 8,
            padding: '10px 14px',
            cursor: 'pointer',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}
        >
          <div>
            <span style={{ fontWeight: 500, fontSize: 13, color: 'var(--color-text-primary)' }}>
              {task.task_name || task.task_id}
            </span>
            <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
              {task.task_id}
            </span>
          </div>
          <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{expanded ? '▲ Hide' : '▼ View'}</span>
        </div>
        {expanded && (
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid var(--color-border)',
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
            padding: '14px',
          }}>
            {renderOutput(task.output)}
          </div>
        )}
      </div>
    </div>
  )
}

function ErrorState({ message, onBack }) {
  return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
      <div style={{ color: 'var(--color-text-muted)', fontSize: 14, marginBottom: 20 }}>{message}</div>
      <button onClick={onBack} style={{
        padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
        border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
        cursor: 'pointer', color: 'var(--color-text-secondary)',
      }}>← Back</button>
    </div>
  )
}