import StatusBadge from '../ui/StatusBadge'

export default function ApprovalCard({ workflow, onApprove, onReject, loading }) {
  const workflowId = workflow.workflow_id || workflow._id || workflow.id

  const title = (workflow.objective_id || workflow.workflow_type || 'Workflow')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())

  // Paused + awaiting input = needs approval
  const needsApproval = workflow.awaiting_human_input === true || workflow.status === 'paused'
  const badgeLabel = needsApproval ? 'Awaiting Approval' : (workflow.status || 'pending')
  const badgeColor = needsApproval ? '#F59E0B' : undefined

  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      border: '1px solid var(--color-border)',
      borderLeft: '4px solid #F59E0B',
      borderRadius: 'var(--radius-lg)',
      padding: '16px 20px',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)', marginBottom: 4 }}>
            {title}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            ID: {workflowId}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
            Created: {workflow.created_at ? new Date(workflow.created_at).toLocaleString() : '—'}
          </div>
        </div>
        <StatusBadge label={badgeLabel} color={badgeColor} />
      </div>

      {workflow.result && (
        <div style={{
          background: 'var(--color-warning-bg)',
          border: '1px solid var(--color-warning-border)',
          borderRadius: 'var(--radius-md)',
          padding: '10px 12px',
          fontSize: 13,
          color: 'var(--color-text-primary)',
          lineHeight: 1.6,
          marginBottom: 14,
          maxHeight: 120,
          overflowY: 'auto',
        }}>
          {typeof workflow.result === 'string'
            ? workflow.result
            : JSON.stringify(workflow.result, null, 2)}
        </div>
      )}

      {workflow.error_message && (
        <div style={{
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 'var(--radius-md)', padding: '10px 12px',
          fontSize: 12, color: '#EF4444', marginBottom: 14,
        }}>
          {workflow.error_message}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => onApprove(workflowId)}
          disabled={loading}
          style={{
            padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
            background: 'var(--color-success-text)', color: '#fff',
            opacity: loading ? 0.6 : 1,
          }}
        >
          ✓ Approve
        </button>
        <button
          onClick={() => onReject(workflowId)}
          disabled={loading}
          style={{
            padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: '1px solid var(--color-danger-border)',
            cursor: loading ? 'not-allowed' : 'pointer',
            background: 'var(--color-danger-bg)', color: 'var(--color-danger-text)',
            opacity: loading ? 0.6 : 1,
          }}
        >
          ✕ Reject
        </button>
      </div>
    </div>
  )
}