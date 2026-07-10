import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
      padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 500,
      background: `${meta.color}18`, color: meta.color,
      border: `1px solid ${meta.color}30`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
      {meta.label}
    </span>
  )
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ width: 160, flexShrink: 0, fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 500, paddingTop: 1 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, color: 'var(--color-text-primary)', flex: 1, wordBreak: 'break-word' }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function DocumentDetail() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [doc, setDoc]         = useState(null)
  const [loading, setLoading] = useState(true)
  const [drafts, setDrafts]   = useState([])

  useEffect(() => {
    Promise.all([
      documentsApi.getOne(documentId),
      documentsApi.listDrafts({ document_id: documentId }),
    ])
      .then(([docRes, draftRes]) => {
        setDoc(docRes)
        setDrafts(draftRes?.items || [])
      })
      .catch(err => toast.error('Failed to load document', err.message))
      .finally(() => setLoading(false))
  }, [documentId])

  if (loading) return <PageLoader />
  if (!doc) return <div style={{ padding: 40, color: 'var(--color-text-muted)' }}>Document not found.</div>

  const summary = doc.processing_result?.ai_summary
  const extractedData = doc.processing_result?.extracted_data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 800 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/documents')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', flex: 1 }}>
          {doc.original_filename}
        </h2>
        <StatusPill status={doc.status} />
      </div>

      {/* Metadata card */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: '20px 24px',
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
          Document Info
        </div>
        <InfoRow label="Document ID"    value={<span style={{ fontFamily: 'monospace', fontSize: 12 }}>{doc.document_id}</span>} />
        <InfoRow label="Document Type"  value={doc.document_type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} />
        <InfoRow label="Business Domain" value={doc.business_domain} />
        <InfoRow label="Outcome"        value={doc.outcome} />
        <InfoRow label="Uploaded By"    value={doc.uploaded_by} />
        <InfoRow label="Uploaded At"    value={doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : null} />
        <InfoRow label="Updated At"     value={doc.updated_at ? new Date(doc.updated_at).toLocaleString() : null} />
        <InfoRow label="File Size"      value={doc.size_bytes ? `${(doc.size_bytes / 1024).toFixed(1)} KB` : null} />
        {doc.target_context && Object.keys(doc.target_context).length > 0 && (
          <InfoRow label="Target Context" value={
            Object.entries(doc.target_context).map(([k, v]) => `${k}: ${v}`).join(' · ')
          } />
        )}
        {doc.error_message && (
          <div style={{ marginTop: 10, padding: '10px 14px', background: 'rgba(239,68,68,0.08)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.2)', fontSize: 13, color: '#EF4444' }}>
            {doc.error_message}
          </div>
        )}
      </div>

      {/* AI Summary */}
      {summary && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '20px 24px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
            AI Summary
            <span style={{ marginLeft: 8, fontSize: 10, color: '#F59E0B', fontWeight: 400, textTransform: 'none' }}>⚠ AI-generated</span>
          </div>
          <p style={{ fontSize: 13.5, color: 'var(--color-text-secondary)', lineHeight: 1.7, margin: 0 }}>{summary}</p>
        </div>
      )}

      {/* Extracted data */}
      {extractedData && Object.keys(extractedData).length > 0 && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '20px 24px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
            Extracted Data
          </div>
          <pre style={{
            fontSize: 12.5, lineHeight: 1.7, color: 'var(--color-text-secondary)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
            fontFamily: 'ui-monospace, monospace',
          }}>
            {JSON.stringify(extractedData, null, 2)}
          </pre>
        </div>
      )}

      {/* Drafts */}
      {drafts.length > 0 && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>
            Import Drafts
          </div>
          {drafts.map((draft, i) => (
            <div
              key={draft.draft_id}
              onClick={() => navigate(`/documents/drafts/${draft.draft_id}`)}
              style={{
                padding: '13px 20px', cursor: 'pointer',
                borderBottom: i < drafts.length - 1 ? '1px solid var(--color-border)' : 'none',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>
                  {draft.target_business_entity} · {draft.operation}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2, fontFamily: 'monospace' }}>
                  {draft.draft_id}
                </div>
              </div>
              <StatusPill status={draft.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}