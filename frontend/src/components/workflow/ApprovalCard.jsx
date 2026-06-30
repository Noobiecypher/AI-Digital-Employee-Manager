import StatusBadge from '../ui/StatusBadge'
import { STATE_META } from '../../constants/workflowStates'

export default function ApprovalCard({ workflow, onApprove, onReject, loading }) {
  const meta = STATE_META[workflow.state] || {}

  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      border: '1px solid var(--color-border)',
      borderLeft: '4px solid var(--color-warning-text)',
      borderRadius: 'var(--radius-lg)',
      padding: '16px 20px',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
            {workflow.workflow_type?.replace(/_/g, ' ')?.replace(/\b\w/g, c => c.toUpperCase()) || 'Workflow'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            ID: {workflow._id || workflow.id}
          </div>
        </div>
        <StatusBadge label={meta.label || workflow.state} color={meta.color} />
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
        }}>
          {typeof workflow.result === 'string'
            ? workflow.result
            : JSON.stringify(workflow.result, null, 2)}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => onApprove(workflow._id || workflow.id)}
          disabled={loading}
          style={{
            padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
            background: 'var(--color-success-text)', color: '#fff',
            opacity: loading ? 0.6 : 1,
          }}
        >
          Approve
        </button>
        <button
          onClick={() => onReject(workflow._id || workflow.id)}
          disabled={loading}
          style={{
            padding: '7px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: '1px solid var(--color-danger-border)',
            cursor: loading ? 'not-allowed' : 'pointer',
            background: 'var(--color-danger-bg)', color: 'var(--color-danger-text)',
            opacity: loading ? 0.6 : 1,
          }}
        >
          Reject
        </button>
      </div>
    </div>
  )
}