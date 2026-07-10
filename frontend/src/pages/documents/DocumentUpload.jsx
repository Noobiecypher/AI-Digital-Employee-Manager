import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { documentsApi } from '../../api/documents'
import { useToast } from '../../components/layout/AppLayout'
import { goalsApi } from '../../api/goals'

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

// Types that require target context (employee_name + review_period)
const CONTEXT_TYPES = ['performance_review', 'self_assessment', 'manager_evaluation']

export default function DocumentUpload() {
  const navigate = useNavigate()
  const toast = useToast()
  const fileRef = useRef()

  const [docTypes, setDocTypes]           = useState([])
  const [selectedType, setSelectedType]   = useState('')
  const [file, setFile]                   = useState(null)
  const [dragOver, setDragOver]           = useState(false)
  const [uploading, setUploading]         = useState(false)
  const [processing, setProcessing]       = useState(false)
  const [uploadResult, setUploadResult]   = useState(null)
  const [processResult, setProcessResult] = useState(null)

  // For context-required types
  const [employees, setEmployees]         = useState([])  // unique employee names from goals
  const [reviewPeriods, setReviewPeriods] = useState([])
  const [selectedEmployee, setSelectedEmployee] = useState('')
  const [selectedPeriod, setSelectedPeriod]     = useState('')

  useEffect(() => {
    documentsApi.getTypes()
      .then(res => setDocTypes(res?.items || []))
      .catch(() => toast.error('Failed to load document types'))
  }, [])

  // Fetch employee names from goals when a context-requiring type is selected
  useEffect(() => {
    if (!CONTEXT_TYPES.includes(selectedType)) return
    goalsApi.getAll()
      .then(res => {
        const goals = res?.items || res || []
        const names = [...new Set(goals.map(g => g.employee_name).filter(Boolean))].sort()
        setEmployees(names)
      })
      .catch(() => {})
  }, [selectedType])

  // Filter review periods for selected employee
  useEffect(() => {
    if (!selectedEmployee) { setReviewPeriods([]); setSelectedPeriod(''); return }
    goalsApi.getAll()
      .then(res => {
        const goals = res?.items || res || []
        const periods = [...new Set(
          goals
            .filter(g => g.employee_name === selectedEmployee)
            .map(g => g.review_period)
            .filter(Boolean)
        )].sort()
        setReviewPeriods(periods)
        setSelectedPeriod('')
      })
      .catch(() => {})
  }, [selectedEmployee])

  const selectedTypeConfig = docTypes.find(t => t.document_type === selectedType)
  const needsContext = CONTEXT_TYPES.includes(selectedType)
  const supportedFormats = selectedTypeConfig?.supported_formats || []

  const canUpload = file && selectedType &&
    (!needsContext || (selectedEmployee && selectedPeriod))

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    setUploadResult(null)
    setProcessResult(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleUpload = async () => {
    if (!canUpload) return
    setUploading(true)
    try {
      const targetContext = needsContext
        ? { employee_name: selectedEmployee, review_period: selectedPeriod }
        : null
      const res = await documentsApi.upload(file, selectedType, targetContext)
      setUploadResult(res)
      toast.success('Uploaded', 'Document classified successfully')
      // Auto-process immediately
      setProcessing(true)
      try {
        const proc = await documentsApi.process(res.document_id)
        setProcessResult(proc)
        toast.success('Processed', proc.draft_id
          ? 'Draft created — go to Drafts to review'
          : 'Document processed successfully')
      } catch (err) {
        toast.error('Processing failed', err.message)
      } finally {
        setProcessing(false)
      }
    } catch (err) {
      toast.error('Upload failed', err.message)
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setUploadResult(null)
    setProcessResult(null)
    setSelectedType('')
    setSelectedEmployee('')
    setSelectedPeriod('')
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div style={{ maxWidth: 680, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={() => navigate('/documents')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          cursor: 'pointer', color: 'var(--color-text-secondary)',
        }}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Upload Document</h2>
      </div>

      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)', padding: '28px 32px',
        display: 'flex', flexDirection: 'column', gap: 22,
      }}>
        {/* Step 1 — Document type */}
        <div>
          <label style={labelStyle}>Document Type *</label>
          <select
            value={selectedType}
            onChange={e => { setSelectedType(e.target.value); setFile(null); setUploadResult(null); setProcessResult(null) }}
            style={selectStyle}
          >
            <option value="">Select a document type...</option>
            {docTypes.map(t => (
              <option key={t.document_type} value={t.document_type}>
                {t.document_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                {' '}· {t.business_domain}
              </option>
            ))}
          </select>
          {selectedTypeConfig && (
            <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 6 }}>
              Supported formats: {supportedFormats.join(', ').toUpperCase()}
              {selectedTypeConfig.review_required && (
                <span style={{ marginLeft: 10, color: '#F59E0B' }}>· Human review required</span>
              )}
            </div>
          )}
        </div>

        {/* Step 2 — Target context (performance types only) */}
        {needsContext && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div>
              <label style={labelStyle}>Employee *</label>
              <select
                value={selectedEmployee}
                onChange={e => setSelectedEmployee(e.target.value)}
                style={selectStyle}
              >
                <option value="">Select employee...</option>
                {employees.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Review Period *</label>
              <select
                value={selectedPeriod}
                onChange={e => setSelectedPeriod(e.target.value)}
                disabled={!selectedEmployee}
                style={{ ...selectStyle, opacity: selectedEmployee ? 1 : 0.5 }}
              >
                <option value="">Select period...</option>
                {reviewPeriods.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Step 3 — File drop zone */}
        {selectedType && (
          <div>
            <label style={labelStyle}>File *</label>
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? '#6366F1' : file ? '#10B981' : 'rgba(255,255,255,0.12)'}`,
                borderRadius: 10, padding: '32px 24px',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
                cursor: 'pointer', transition: 'all 0.15s',
                background: dragOver ? 'rgba(99,102,241,0.06)' : file ? 'rgba(16,185,129,0.04)' : 'rgba(255,255,255,0.01)',
              }}
            >
              <div style={{ fontSize: 28 }}>{file ? '✅' : '📄'}</div>
              {file ? (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-text-primary)' }}>{file.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 3 }}>
                    {(file.size / 1024).toFixed(1)} KB
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 13.5, color: 'var(--color-text-secondary)' }}>
                    Drop file here or click to browse
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>
                    {supportedFormats.length > 0
                      ? `Accepted: ${supportedFormats.join(', ').toUpperCase()}`
                      : 'Any file type'}
                  </div>
                </div>
              )}
            </div>
            <input
              ref={fileRef} type="file" style={{ display: 'none' }}
              accept={supportedFormats.map(f => `.${f}`).join(',')}
              onChange={e => handleFile(e.target.files[0])}
            />
          </div>
        )}

        {/* Result state */}
        {(uploadResult || processing) && (
          <div style={{
            background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)',
            borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                {uploadResult?.original_filename}
              </span>
              {uploadResult && <StatusPill status={processResult?.status || uploadResult?.status} />}
            </div>
            {uploadResult && (
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                ID: {uploadResult.document_id}
              </div>
            )}
            {processing && (
              <div style={{ fontSize: 12.5, color: '#F59E0B', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
                Processing document...
              </div>
            )}
            {processResult?.draft_id && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12.5, color: '#10B981' }}>
                  ✓ Draft created — review required before import
                </span>
                <button
                  onClick={() => navigate(`/documents/drafts/${processResult.draft_id}`)}
                  style={{
                    padding: '5px 14px', borderRadius: 7, fontSize: 12, fontWeight: 500,
                    background: 'rgba(99,102,241,0.15)', color: '#818CF8',
                    border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer',
                  }}
                >
                  Review Draft →
                </button>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
          {uploadResult && (
            <button onClick={reset} style={{
              padding: '9px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
              border: '1px solid var(--color-border)', background: 'transparent',
              color: 'var(--color-text-secondary)', cursor: 'pointer',
            }}>Upload Another</button>
          )}
          {!uploadResult && (
            <>
              <button onClick={() => navigate('/documents')} style={{
                padding: '9px 18px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: '1px solid var(--color-border)', background: 'transparent',
                color: 'var(--color-text-secondary)', cursor: 'pointer',
              }}>Cancel</button>
              <button
                onClick={handleUpload}
                disabled={!canUpload || uploading}
                style={{
                  padding: '9px 24px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                  border: 'none',
                  background: canUpload ? 'linear-gradient(135deg, #6366F1, #4F46E5)' : 'rgba(255,255,255,0.08)',
                  color: canUpload ? '#fff' : 'var(--color-text-muted)',
                  cursor: canUpload && !uploading ? 'pointer' : 'not-allowed',
                  opacity: uploading ? 0.7 : 1,
                  boxShadow: canUpload ? '0 0 16px rgba(99,102,241,0.25)' : 'none',
                }}
              >
                {uploading ? 'Uploading...' : '⬆ Upload & Process'}
              </button>
            </>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const labelStyle = {
  fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)',
  display: 'block', marginBottom: 7, letterSpacing: '0.03em', textTransform: 'uppercase',
}

const selectStyle = {
  width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13.5,
  border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
  color: 'var(--color-text-primary)', outline: 'none', cursor: 'pointer',
  boxSizing: 'border-box',
}