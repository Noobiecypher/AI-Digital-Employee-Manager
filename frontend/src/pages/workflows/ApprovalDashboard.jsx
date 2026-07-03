import { useState, useEffect, useRef } from 'react'
import { workflowsApi } from '../../api/workflows'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import ApprovalCard from '../../components/workflow/ApprovalCard'
import { useToast } from '../../components/layout/AppLayout'

const POLL_INTERVAL_MS = 4000

export default function ApprovalDashboard() {
  const toast = useToast()
  const [pending, setPending]             = useState([])
  const [loading, setLoading]             = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const intervalRef                       = useRef(null)

  const load = async (showLoader = false) => {
    if (showLoader) setLoading(true)
    try {
      const res = await workflowsApi.getPending()
      setPending(Array.isArray(res) ? res : [])
    } catch (err) {
      toast.error('Failed to load', err.message)
      setPending([])
    } finally {
      if (showLoader) setLoading(false)
    }
  }

  useEffect(() => {
    // Initial load with spinner
    load(true)
    // Poll every 4s so the page updates when a workflow pauses
    intervalRef.current = setInterval(() => load(false), POLL_INTERVAL_MS)
    return () => clearInterval(intervalRef.current)
  }, [])

  const handleApprove = async (id) => {
    setActionLoading(true)
    clearInterval(intervalRef.current) // pause polling during action
    try {
      await workflowsApi.approve(id)
      toast.success('Approved', 'Workflow will continue running')
      await load(false)
    } catch (err) {
      toast.error('Approval failed', err.message)
    } finally {
      setActionLoading(false)
      // Resume polling
      intervalRef.current = setInterval(() => load(false), POLL_INTERVAL_MS)
    }
  }

  const handleReject = async (id) => {
    setActionLoading(true)
    clearInterval(intervalRef.current)
    try {
      await workflowsApi.reject(id)
      toast.success('Rejected', 'Workflow has been stopped')
      await load(false)
    } catch (err) {
      toast.error('Rejection failed', err.message)
    } finally {
      setActionLoading(false)
      intervalRef.current = setInterval(() => load(false), POLL_INTERVAL_MS)
    }
  }

  if (loading) return <PageLoader />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            Pending Approvals
          </h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
            {pending.length} workflow{pending.length !== 1 ? 's' : ''} waiting for your review
          </p>
        </div>
        {/* Live indicator */}
        <span style={{ fontSize: 11, color: '#818CF8', display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: 'currentColor',
            display: 'inline-block', animation: 'pulse 1.5s infinite',
          }} />
          Live
          <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
        </span>
      </div>

      {pending.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 56, textAlign: 'center',
          boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>✅</div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6, color: 'var(--color-text-primary)' }}>
            All caught up
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            No workflows are waiting for your approval
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {pending.map((wf, i) => (
            <ApprovalCard
              key={wf.workflow_id || wf._id || i}
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