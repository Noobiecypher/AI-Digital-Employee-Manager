import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { workflowsApi } from '../../api/workflows'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import StatusBadge from '../../components/ui/StatusBadge'
import { STATE_META } from '../../constants/workflowStates'
import { useToast } from '../../components/layout/AppLayout'

function getStatus(wf) {
  if (wf.awaiting_human_input) return 'waiting_for_human'
  return wf.status || wf.state || 'pending'
}

function getStatusMeta(wf) {
  const status = getStatus(wf)
  return STATE_META[status] || { label: status, color: 'default' }
}

export default function WorkflowDashboard() {
  const navigate = useNavigate()
  const toast = useToast()
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading]     = useState(true)
  const [filter, setFilter]       = useState('all')

  useEffect(() => {
    workflowsApi.getAll()
      .then(res => {
        const arr = Array.isArray(res) ? res : res?.items || res?.workflows || []
        setWorkflows(arr)
      })
      .catch(err => {
        toast.error('Failed to load workflows', err.message)
        setWorkflows([])
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageLoader />

  const counts = {
    all:               workflows.length,
    running:           workflows.filter(w => getStatus(w) === 'running').length,
    waiting_for_human: workflows.filter(w => getStatus(w) === 'waiting_for_human').length,
    completed:         workflows.filter(w => getStatus(w) === 'completed').length,
    failed:            workflows.filter(w => getStatus(w) === 'failed').length,
  }

  const filtered = filter === 'all' ? workflows : workflows.filter(w => getStatus(w) === filter)
  const sorted   = [...filtered].reverse()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Workflows</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{workflows.length} total executions</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => navigate('/workflows/history')} style={{
            padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
            color: 'var(--color-text-secondary)', cursor: 'pointer',
          }}>History</button>
          <button onClick={() => navigate('/workflows/start')} style={{
            padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
            color: '#fff', border: 'none', cursor: 'pointer',
            boxShadow: '0 0 14px rgba(99,102,241,0.25)',
          }}>+ Start Workflow</button>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {[
          { key: 'all',               label: 'All' },
          { key: 'running',           label: 'Running' },
          { key: 'waiting_for_human', label: 'Needs Approval' },
          { key: 'completed',         label: 'Completed' },
          { key: 'failed',            label: 'Failed' },
        ].map(tab => (
          <button key={tab.key} onClick={() => setFilter(tab.key)} style={{
            padding: '6px 14px', borderRadius: 20, fontSize: 12.5, fontWeight: 500, cursor: 'pointer',
            border: '1px solid',
            borderColor: filter === tab.key ? '#6366F1' : 'var(--color-border)',
            background:  filter === tab.key ? 'rgba(99,102,241,0.15)' : 'transparent',
            color:       filter === tab.key ? '#818CF8' : 'var(--color-text-secondary)',
          }}>
            {tab.label}
            <span style={{
              marginLeft: 6, padding: '1px 6px', borderRadius: 10, fontSize: 11,
              background: filter === tab.key ? '#6366F1' : 'rgba(255,255,255,0.08)',
              color: filter === tab.key ? '#fff' : 'var(--color-text-muted)',
            }}>{counts[tab.key]}</span>
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 56, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⚡</div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: 14, marginBottom: 16 }}>No workflows yet</div>
          <button onClick={() => navigate('/workflows/start')} style={{
            padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
            color: '#fff', border: 'none', cursor: 'pointer',
          }}>Start your first workflow</button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sorted.map((wf, i) => {
            const id     = wf.workflow_id || wf._id || wf.id
            const type   = wf.objective_id || wf.workflow_type || ''
            const status = getStatus(wf)
            const meta   = getStatusMeta(wf)
            const dotColor = status === 'completed' ? '#10B981'
              : status === 'failed' ? '#EF4444'
              : status === 'running' ? '#6366F1'
              : status === 'waiting_for_human' ? '#F59E0B'
              : '#475569'

            return (
              <div key={id || i} onClick={() => navigate(`/workflows/${id}`)} style={{
                background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)', padding: '14px 20px',
                display: 'flex', alignItems: 'center', gap: 16,
                cursor: 'pointer', transition: 'background 0.1s',
              }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--color-bg-surface-2)'}
                onMouseLeave={e => e.currentTarget.style.background = 'var(--color-bg-surface)'}
              >
                <div style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                  background: dotColor,
                  boxShadow: status === 'running' ? `0 0 6px ${dotColor}` : 'none',
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: 13.5, color: 'var(--color-text-primary)' }}>
                    {type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Workflow'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2, fontFamily: 'monospace' }}>
                    {id}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 1 }}>
                    {wf.created_at ? new Date(wf.created_at).toLocaleString() : ''}
                  </div>
                </div>
                <StatusBadge label={meta.label || status} color={meta.color} />
                <span style={{ fontSize: 12, color: 'var(--color-text-muted)', flexShrink: 0 }}>View →</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}