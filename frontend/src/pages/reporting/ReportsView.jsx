import { useState, useEffect } from 'react'
import { reportsApi } from '../../api/reports'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

export default function ReportsView() {
  const toast = useToast()
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    reportsApi.getReports()
      .then(res => { const arr = res?.reports || res || []; setReports(arr); if (arr.length) setSelected(arr[0]) })
      .catch(err => toast.error('Failed to load reports', err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageLoader />

  if (reports.length === 0) return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <div style={{ fontSize: 36, marginBottom: 12 }}>📄</div>
      <div style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>No reports generated yet. Run a workflow to generate reports.</div>
    </div>
  )

  return (
    <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 120px)' }}>
      {/* Sidebar list */}
      <div style={{
        width: 260, flexShrink: 0,
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 14 }}>
          Generated Reports
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {reports.map((r, i) => (
            <div
              key={i}
              onClick={() => setSelected(r)}
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                background: selected === r ? 'var(--color-primary-light)' : 'transparent',
                borderLeft: selected === r ? '3px solid var(--color-primary)' : '3px solid transparent',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 500, color: selected === r ? 'var(--color-primary-dark)' : 'var(--color-text-primary)' }}>
                {r.title || r.workflow_type?.replace(/_/g, ' ')?.replace(/\b\w/g, c => c.toUpperCase()) || `Report ${i + 1}`}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3 }}>
                {r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Report content */}
      <div style={{
        flex: 1, background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden', boxShadow: 'var(--shadow-sm)',
        display: 'flex', flexDirection: 'column',
      }}>
        {selected ? (
          <>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                {selected.title || 'Report'}
              </span>
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: 'var(--color-warning-bg)', color: 'var(--color-warning-text)', fontWeight: 500 }}>
                ⚠ AI-generated
              </span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
              <pre style={{
                fontSize: 13.5, lineHeight: 1.8,
                color: 'var(--color-text-secondary)',
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                margin: 0, fontFamily: 'inherit',
              }}>
                {typeof selected.content === 'string'
                  ? selected.content
                  : JSON.stringify(selected, null, 2)}
              </pre>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--color-text-muted)', fontSize: 13 }}>
            Select a report to view
          </div>
        )}
      </div>
    </div>
  )
}