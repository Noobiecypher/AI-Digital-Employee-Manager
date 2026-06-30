import { useState, useEffect } from 'react'
import { workflowsApi } from '../../api/workflows'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import ApprovalCard from '../../components/workflow/ApprovalCard'
import { useToast } from '../../components/layout/AppLayout'

export default function ApprovalDashboard() {
  const toast = useToast()
  const [pending, setPending]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  const load = async () => {
    try {
      const res = await workflowsApi.getPending()
      setPending(res?.workflows || res || [])
    } catch {
      // fallback: get all and filter
      try {
        const all = await workflowsApi.getAll()
        const wfs = all?.workflows || all || []
        setPending(wfs.filter(w => w.state === 'waiting_for_human'))
      } catch (err) {
        toast.error('Failed to load', err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleApprove = async (id) => {
    setActionLoading(true)
    try {
      await workflowsApi.approve(id, { approved: true })
      toast.success('Approved', 'Workflow will continue running')
      load()
    } catch (err) {
      toast.error('Approval failed', err.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (id) => {
    setActionLoading(true)
    try {
      await workflowsApi.reject(id, { approved: false })
      toast.success('Rejected', 'Workflow has been stopped')
      load()
    } catch (err) {
      toast.error('Rejection failed', err.message)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <PageLoader />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700 }}>Pending Approvals</h2>
        <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
          {pending.length} workflow{pending.length !== 1 ? 's' : ''} waiting for your review
        </p>
      </div>

      {pending.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 56, textAlign: 'center',
          boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>✅</div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>All caught up</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No workflows are waiting for your approval</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {pending.map((wf, i) => (
            <ApprovalCard
              key={wf._id || i}
              workflow={wf}
              onApprove={handleApprove}
              onReject={handleReject}
              loading={actionLoading}
            />
          ))}
        </div>
      )}
    </div>
  )
}