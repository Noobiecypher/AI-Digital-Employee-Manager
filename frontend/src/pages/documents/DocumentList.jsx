import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { documentsApi } from '../../api/documents'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

const STATUS_META = {
  classified:     { label: 'Classified',     color: '#06B6D4' },
  processed:      { label: 'Processed',      color: '#10B981' },
  pending_review: { label: 'Pending Review', color: '#F59E0B' },
  approved:       { label: 'Approved',       color: '#10B981' },
  rejected:       { label: 'Rejected',       color: '#EF4444' },
  failed:         { label: 'Failed',         color: '#EF4444' },
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
  { key: 'classified', label: 'Classified' },
  { key: 'processed', label: 'Processed' },
  { key: 'pending_review', label: 'Pending Review' },
  { key: 'approved', label: 'Approved' },
  { key: 'imported', label: 'Imported' },
  { key: 'failed', label: 'Failed' },
]

export default function DocumentList() {
  const navigate = useNavigate()
  const toast = useToast()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading]     = useState(true)
  const [filter, setFilter]       = useState('')
  const [deleting, setDeleting]   = useState(null)

  const load = () => {
    setLoading(true)
    documentsApi.list({ status: filter || undefined, limit: 100 })
      .then(res => setDocuments(res?.items || []))
      .catch(err => toast.error('Failed to load documents', err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter])

  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.original_filename}"?`)) return
    setDeleting(doc.document_id)
    try {
      await documentsApi.delete(doc.document_id)
      toast.success('Deleted', doc.original_filename)
      load()
    } catch (err) {
      toast.error('Cannot delete', err.message)
    } finally {
      setDeleting(null)
    }
  }

  // Pending review count for banner
  const pendingCount = documents.filter(d => d.status === 'pending_review').length

  if (loading) return <PageLoader />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Documents</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
            {documents.length} document{documents.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => navigate('/documents/drafts')} style={{
            padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
            color: 'var(--color-text-secondary)', cursor: 'pointer',
          }}>
            Drafts {pendingCount > 0 && (
              <span style={{
                marginLeft: 6, padding: '1px 7px', borderRadius: 10, fontSize: 11,
                background: '#F59E0B', color: '#000', fontWeight: 700,
              }}>{pendingCount}</span>
            )}
          </button>
          <button onClick={() => navigate('/documents/upload')} style={{
            padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
            color: '#fff', border: 'none', cursor: 'pointer',
            boxShadow: '0 0 14px rgba(99,102,241,0.25)',
          }}>+ Upload Document</button>
        </div>
      </div>

      {pendingCount > 0 && (
        <div
          onClick={() => navigate('/documents/drafts')}
          style={{
            background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
            borderRadius: 'var(--radius-lg)', padding: '12px 18px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#F59E0B', boxShadow: '0 0 6px #F59E0B' }} />
            <span style={{ fontWeight: 500, color: '#F59E0B', fontSize: 13 }}>
              {pendingCount} draft{pendingCount > 1 ? 's' : ''} waiting for review
            </span>
          </div>
          <span style={{ fontSize: 12, color: '#F59E0B', opacity: 0.8 }}>Review →</span>
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
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

      {documents.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 56, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📄</div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: 14, marginBottom: 16 }}>
            No documents yet
          </div>
          <button onClick={() => navigate('/documents/upload')} style={{
            padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
            color: '#fff', border: 'none', cursor: 'pointer',
          }}>Upload your first document</button>
        </div>
      ) : (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg-surface-2)' }}>
                {['File', 'Type', 'Domain', 'Status', 'Uploaded', ''].map(h => (
                  <th key={h} style={{
                    padding: '10px 16px', textAlign: 'left',
                    fontSize: 11, fontWeight: 600,
                    color: 'var(--color-text-muted)',
                    textTransform: 'uppercase', letterSpacing: '0.07em',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc, i) => (
                <tr
                  key={doc.document_id}
                  style={{ borderBottom: i < documents.length - 1 ? '1px solid var(--color-border)' : 'none', cursor: 'pointer' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  onClick={() => navigate(`/documents/${doc.document_id}`)}
                >
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontWeight: 500, color: 'var(--color-text-primary)', fontSize: 13 }}>
                      {doc.original_filename}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2, fontFamily: 'monospace' }}>
                      {doc.document_id?.slice(0, 16)}…
                    </div>
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontSize: 12.5 }}>
                    {doc.document_type
                      ? doc.document_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                      : <span style={{ color: 'var(--color-text-muted)' }}>—</span>}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontSize: 12.5, textTransform: 'capitalize' }}>
                    {doc.business_domain || '—'}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <StatusPill status={doc.status} />
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                    {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: '12px 16px' }} onClick={e => e.stopPropagation()}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {doc.status === 'pending_review' && (
                        <button
                          onClick={() => navigate(`/documents/drafts?document_id=${doc.document_id}`)}
                          style={actionBtnStyle('#F59E0B')}
                        >Review</button>
                      )}
                      <button
                        onClick={() => handleDelete(doc)}
                        disabled={deleting === doc.document_id}
                        style={actionBtnStyle('#EF4444')}
                      >Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const actionBtnStyle = (color) => ({
  padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500, cursor: 'pointer',
  border: `1px solid ${color}30`, background: `${color}10`, color,
})