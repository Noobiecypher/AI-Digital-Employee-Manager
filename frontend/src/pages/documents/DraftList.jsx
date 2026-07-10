import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { documentsApi } from '../../api/documents'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

const STATUS_META = {
  pending_review: { label: 'Pending Review', color: '#F59E0B' },
  approved:       { label: 'Approved',       color: '#10B981' },
  rejected:       { label: 'Rejected',       color: '#EF4444' },
  imported:       { label: 'Imported',       color: '#8B5CF6' },
}

function StatusPill({ status }) {
  const meta = STATUS_META[status] || { label: status, color: '#475569' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20, fontSize: 11.5, fontWeight: 500,
      background: `${meta.color}18`, color: meta.color,
      border: `1px solid ${meta.color}30`,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor' }} />
      {meta.label}
    </span>
  )
}

const FILTERS = [
  { key: '', label: 'All' },
  { key: 'pending_review', label: 'Pending Review' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'imported', label: 'Imported' },
]

export default function DraftList() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const toast = useToast()
  const [drafts, setDrafts]   = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('')

  const documentIdFilter = searchParams.get('document_id')

  useEffect(() => {
    setLoading(true)
    documentsApi.listDrafts({
      status: filter || undefined,
      document_id: documentIdFilter || undefined,
    })
      .then(res => setDrafts(res?.items || []))
      .catch(err => toast.error('Failed to load drafts', err.message))
      .finally(() => setLoading(false))
  }, [filter, documentIdFilter])

  if (loading) return <PageLoader />

  const pendingCount = drafts.filter(d => d.status === 'pending_review').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button onClick={() => navigate('/documents')} style={{
              padding: '5px 10px', borderRadius: 7, fontSize: 12,
              border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
              cursor: 'pointer', color: 'var(--color-text-secondary)',
            }}>← Documents</button>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              Import Drafts
            </h2>
          </div>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>
            {drafts.length} draft{drafts.length !== 1 ? 's' : ''}
            {pendingCount > 0 && ` · ${pendingCount} pending review`}
          </p>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6 }}>
        {FILTERS.map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding: '6px 14px', borderRadius: 20, fontSize: 12.5, fontWeight: 500, cursor: 'pointer',
            border: '1px solid',
            borderColor: filter === f.key ? '#6366F1' : 'var(--color-border)',
            background: filter === f.key ? 'rgba(99,102,241,0.15)' : 'transparent',
            color: filter === f.key ? '#818CF8' : 'var(--color-text-secondary)',
          }}>{f.label}</button>
        ))}
      </div>

      {drafts.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 56, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>No drafts found</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {drafts.map(draft => (
            <div
              key={draft.draft_id}
              onClick={() => navigate(`/documents/drafts/${draft.draft_id}`)}
              style={{
                background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
                borderLeft: draft.status === 'pending_review' ? '4px solid #F59E0B' : '4px solid transparent',
                borderRadius: 'var(--radius-lg)', padding: '16px 20px',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                cursor: 'pointer', transition: 'background 0.1s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--color-bg-surface-2)'}
              onMouseLeave={e => e.currentTarget.style.background = 'var(--color-bg-surface)'}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 4 }}>
                  {draft.target_business_entity?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 400 }}>
                    {draft.operation}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                  {draft.draft_id}
                </div>
                {draft.ai_summary && (
                  <div style={{ fontSize: 12.5, color: 'var(--color-text-secondary)', marginTop: 6, lineHeight: 1.5, maxWidth: 560 }}>
                    {draft.ai_summary.slice(0, 120)}{draft.ai_summary.length > 120 ? '…' : ''}
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                <StatusPill status={draft.status} />
                {draft.confidence != null && (
                  <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                    {Math.round(draft.confidence * 100)}% confidence
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}