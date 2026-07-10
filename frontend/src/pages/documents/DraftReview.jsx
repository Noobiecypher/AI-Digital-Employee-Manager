import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
      padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 500,
      background: `${meta.color}18`, color: meta.color,
      border: `1px solid ${meta.color}30`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
      {meta.label}
    </span>
  )
}

// Render one field from the requirements contract
function FieldInput({ field, value, onChange }) {
  const baseStyle = {
    width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
    border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
    color: 'var(--color-text-primary)', outline: 'none', boxSizing: 'border-box',
  }

  if (field.input_type === 'tag_list') {
    const arr = Array.isArray(value) ? value : []
    return (
      <div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
          {arr.map((tag, i) => (
            <span key={i} style={{
              padding: '3px 10px', borderRadius: 20, fontSize: 12,
              background: 'rgba(99,102,241,0.12)', color: '#818CF8',
              border: '1px solid rgba(99,102,241,0.25)',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
              {tag}
              <button
                onClick={() => onChange(arr.filter((_, j) => j !== i))}
                style={{ background: 'none', border: 'none', color: '#818CF8', cursor: 'pointer', padding: 0, fontSize: 13, lineHeight: 1 }}
              >×</button>
            </span>
          ))}
        </div>
        <input
          placeholder="Type and press Enter to add..."
          style={baseStyle}
          onKeyDown={e => {
            if (e.key === 'Enter' && e.target.value.trim()) {
              onChange([...arr, e.target.value.trim()])
              e.target.value = ''
            }
          }}
        />
      </div>
    )
  }

  if (field.input_type === 'number') {
    return (
      <input
        type="number"
        value={value ?? ''}
        min={field.constraints?.minimum}
        max={field.constraints?.maximum}
        onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
        style={baseStyle}
      />
    )
  }

  if (field.input_type === 'textarea') {
    return (
      <textarea
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        rows={3}
        style={{ ...baseStyle, resize: 'vertical', lineHeight: 1.6 }}
      />
    )
  }

  // Default: text
  return (
    <input
      type="text"
      value={value ?? ''}
      maxLength={field.constraints?.maxLength}
      onChange={e => onChange(e.target.value)}
      style={baseStyle}
    />
  )
}

export default function DraftReview() {
  const { draftId } = useParams()
  const navigate    = useNavigate()
  const toast       = useToast()

  const [draft, setDraft]           = useState(null)
  const [requirements, setReqs]     = useState([])
  const [editedData, setEditedData] = useState({})
  const [loading, setLoading]       = useState(true)
  const [saving, setSaving]         = useState(false)
  const [reviewing, setReviewing]   = useState(false)
  const [importing, setImporting]   = useState(false)
  const [notes, setNotes]           = useState('')
  const [showRejectModal, setShowRejectModal] = useState(false)

  useEffect(() => {
    Promise.all([
      documentsApi.getDraft(draftId),
      documentsApi.getDraftRequirements(draftId),
    ])
      .then(([draftRes, reqRes]) => {
        setDraft(draftRes)
        setReqs(reqRes?.fields || [])
        setEditedData(draftRes.extracted_data || {})
      })
      .catch(err => toast.error('Failed to load draft', err.message))
      .finally(() => setLoading(false))
  }, [draftId])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await documentsApi.updateDraft(draftId, editedData)
      setDraft(updated)
      toast.success('Saved', 'Draft data updated')
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    setReviewing(true)
    try {
      await documentsApi.reviewDraft(draftId, 'approved', notes || null)
      const updated = await documentsApi.getDraft(draftId)
      setDraft(updated)
      toast.success('Approved', 'Draft approved — you can now import it')
    } catch (err) {
      toast.error('Approval failed', err.message)
    } finally {
      setReviewing(false)
    }
  }

  const handleReject = async () => {
    setReviewing(true)
    try {
      await documentsApi.reviewDraft(draftId, 'rejected', notes || null)
      const updated = await documentsApi.getDraft(draftId)
      setDraft(updated)
      setShowRejectModal(false)
      toast.success('Rejected', 'Draft has been rejected')
    } catch (err) {
      toast.error('Rejection failed', err.message)
    } finally {
      setReviewing(false)
    }
  }

  const handleImport = async () => {
    setImporting(true)
    try {
      const res = await documentsApi.importDraft(draftId)
      toast.success('Imported', `${res.target_business_entity} created successfully`)
      navigate('/documents')
    } catch (err) {
      toast.error('Import failed', err.message)
    } finally {
      setImporting(false)
    }
  }

  if (loading) return <PageLoader />
  if (!draft)  return <div style={{ padding: 40, color: 'var(--color-text-muted)' }}>Draft not found.</div>

  const isPending  = draft.status === 'pending_review'
  const isApproved = draft.status === 'approved'
  const isImported = draft.status === 'imported'
  const sortedReqs = [...requirements].sort((a, b) => a.order - b.order)
  const hasRequirements = sortedReqs.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 780 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/documents/drafts')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Drafts</button>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', flex: 1 }}>
          Review Draft
        </h2>
        <StatusPill status={draft.status} />
      </div>

      {/* Summary card */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)', padding: '18px 22px',
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 20px',
      }}>
        {[
          ['Draft ID',     <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{draft.draft_id}</span>],
          ['Entity',       draft.target_business_entity?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())],
          ['Operation',    draft.operation],
          ['Domain',       draft.business_domain],
          ['Confidence',   draft.confidence != null ? `${Math.round(draft.confidence * 100)}%` : '—'],
          ['Created',      draft.created_at ? new Date(draft.created_at).toLocaleString() : '—'],
        ].map(([label, value]) => (
          <div key={label}>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 500, marginBottom: 2 }}>{label}</div>
            <div style={{ fontSize: 13, color: 'var(--color-text-primary)' }}>{value}</div>
          </div>
        ))}
        {draft.ai_summary && (
          <div style={{ gridColumn: '1 / -1', marginTop: 6, paddingTop: 10, borderTop: '1px solid var(--color-border)' }}>
            <div style={{ fontSize: 11, color: '#F59E0B', fontWeight: 500, marginBottom: 4 }}>⚠ AI Summary</div>
            <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>{draft.ai_summary}</div>
          </div>
        )}
      </div>

      {/* Editable fields from requirements contract */}
      {hasRequirements && isPending && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '20px 24px',
          display: 'flex', flexDirection: 'column', gap: 18,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
              Review & Edit Extracted Data
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                padding: '7px 16px', borderRadius: 7, fontSize: 12.5, fontWeight: 500,
                border: '1px solid rgba(99,102,241,0.3)', background: 'rgba(99,102,241,0.12)',
                color: '#818CF8', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
          {sortedReqs.map(field => (
            <div key={field.field_name}>
              <label style={{
                fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)',
                display: 'block', marginBottom: 6, letterSpacing: '0.02em',
              }}>
                {field.label}
                {field.required && <span style={{ color: '#EF4444', marginLeft: 3 }}>*</span>}
                <span style={{ marginLeft: 6, fontSize: 10.5, color: 'var(--color-text-muted)', fontWeight: 400 }}>
                  {field.field_type}
                </span>
              </label>
              <FieldInput
                field={field}
                value={editedData[field.field_name]}
                onChange={val => setEditedData(prev => ({ ...prev, [field.field_name]: val }))}
              />
            </div>
          ))}
        </div>
      )}

      {/* Raw extracted data (read-only when no requirements or already reviewed) */}
      {(!hasRequirements || !isPending) && draft.extracted_data && Object.keys(draft.extracted_data).length > 0 && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '20px 24px',
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
            Extracted Data
          </div>
          <pre style={{
            fontSize: 12.5, lineHeight: 1.7, color: 'var(--color-text-secondary)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
            fontFamily: 'ui-monospace, monospace',
          }}>
            {JSON.stringify(draft.extracted_data, null, 2)}
          </pre>
        </div>
      )}

      {/* Reviewer notes (shown if already reviewed) */}
      {draft.review_notes && (
        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '16px 20px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 6 }}>
            Reviewer Notes
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', margin: 0 }}>{draft.review_notes}</p>
          {draft.reviewed_by && (
            <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 6 }}>
              By {draft.reviewed_by}
            </div>
          )}
        </div>
      )}

      {/* Action bar */}
      {(isPending || isApproved) && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: '18px 22px',
          display: 'flex', flexDirection: 'column', gap: 14,
        }}>
          {isPending && (
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: 7 }}>
                Reviewer Notes (optional)
              </label>
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Add any notes about your decision..."
                rows={2}
                style={{
                  width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
                  border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
                  color: 'var(--color-text-primary)', outline: 'none', resize: 'vertical',
                  lineHeight: 1.6, boxSizing: 'border-box',
                }}
              />
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            {isPending && (
              <>
                <button
                  onClick={() => setShowRejectModal(true)}
                  disabled={reviewing}
                  style={{
                    padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                    border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)',
                    color: '#EF4444', cursor: 'pointer', opacity: reviewing ? 0.7 : 1,
                  }}
                >Reject</button>
                <button
                  onClick={handleApprove}
                  disabled={reviewing}
                  style={{
                    padding: '9px 24px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                    border: 'none', background: 'linear-gradient(135deg, #10B981, #059669)',
                    color: '#fff', cursor: reviewing ? 'not-allowed' : 'pointer',
                    opacity: reviewing ? 0.7 : 1,
                    boxShadow: '0 0 14px rgba(16,185,129,0.25)',
                  }}
                >
                  {reviewing ? 'Approving...' : '✓ Approve'}
                </button>
              </>
            )}
            {isApproved && (
              <button
                onClick={handleImport}
                disabled={importing}
                style={{
                  padding: '9px 28px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  border: 'none', background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
                  color: '#fff', cursor: importing ? 'not-allowed' : 'pointer',
                  opacity: importing ? 0.7 : 1,
                  boxShadow: '0 0 16px rgba(99,102,241,0.3)',
                }}
              >
                {importing ? 'Importing...' : '⬆ Import into System'}
              </button>
            )}
          </div>
        </div>
      )}

      {isImported && (
        <div style={{
          background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.25)',
          borderRadius: 'var(--radius-lg)', padding: '16px 20px',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ fontSize: 18 }}>✅</span>
          <span style={{ fontSize: 13.5, color: '#A78BFA', fontWeight: 500 }}>
            This draft has been imported into the system.
          </span>
        </div>
      )}

      {/* Reject confirmation modal */}
      {showRejectModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
            borderRadius: 14, padding: '28px 32px', maxWidth: 420, width: '90%',
          }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 10, color: 'var(--color-text-primary)' }}>
              Reject Draft?
            </h3>
            <p style={{ fontSize: 13.5, color: 'var(--color-text-secondary)', marginBottom: 20, lineHeight: 1.6 }}>
              This draft will be rejected and cannot be imported. Add a reason below (optional).
            </p>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Reason for rejection..."
              rows={3}
              style={{
                width: '100%', padding: '9px 12px', borderRadius: 8, fontSize: 13,
                border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)', outline: 'none', resize: 'vertical',
                lineHeight: 1.6, boxSizing: 'border-box', marginBottom: 18,
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowRejectModal(false)}
                style={{
                  padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                  border: '1px solid var(--color-border)', background: 'transparent',
                  color: 'var(--color-text-secondary)', cursor: 'pointer',
                }}
              >Cancel</button>
              <button
                onClick={handleReject}
                disabled={reviewing}
                style={{
                  padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  border: 'none', background: '#EF4444', color: '#fff',
                  cursor: reviewing ? 'not-allowed' : 'pointer', opacity: reviewing ? 0.7 : 1,
                }}
              >
                {reviewing ? 'Rejecting...' : 'Confirm Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}