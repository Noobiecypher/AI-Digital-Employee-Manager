import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { candidatesApi } from '../../api/candidates'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

export default function CandidateDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [candidate, setCandidate] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    candidatesApi.getOne(id)
      .then(setCandidate)
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <PageLoader />
  if (!candidate) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Candidate not found</div>

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => navigate('/candidates')} style={{
          padding: '6px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'transparent', cursor: 'pointer',
        }}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 700, flex: 1 }}>{candidate.name}</h2>
        <button onClick={() => navigate(`/candidates/${id}/edit`)} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          background: 'var(--color-primary)', color: '#fff', border: 'none', cursor: 'pointer',
        }}>Edit</button>
      </div>

      {/* Info card */}
      <SectionCard title="Basic Information">
        <InfoGrid>
          <InfoItem label="Role Applied"     value={candidate.role_applied} />
          <InfoItem label="Experience"       value={candidate.experience_years ? `${candidate.experience_years} years` : null} />
          <InfoItem label="Email"            value={candidate.email} />
          <InfoItem label="Phone"            value={candidate.phone} />
          <InfoItem label="Match Score"      value={candidate.match_score ? `${Math.round(candidate.match_score)}%` : null} />
          <InfoItem label="Candidate ID"     value={candidate.candidate_id || candidate._id} />
        </InfoGrid>
      </SectionCard>

      {/* Skills */}
      {candidate.skills?.length > 0 && (
        <SectionCard title="Skills">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {candidate.skills.map(skill => (
              <span key={skill} style={{
                padding: '4px 12px', borderRadius: 16, fontSize: 13, fontWeight: 500,
                background: 'var(--color-primary-light)', color: 'var(--color-primary-dark)',
              }}>{skill}</span>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Resume section — stubbed until backend is ready */}
      <SectionCard title="Resume">
        <div style={{
          background: '#F9FAFB',
          border: '1px dashed var(--color-border)',
          borderRadius: 'var(--radius-md)',
          padding: '24px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>📄</div>
          <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 4 }}>
            {candidate.resume_filename || 'No resume uploaded'}
          </div>
          {candidate.resume_uploaded_at && (
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
              Uploaded: {new Date(candidate.resume_uploaded_at).toLocaleDateString()}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            <button disabled title="Coming soon" style={{
              padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
              border: '1px solid var(--color-border)', background: 'transparent',
              cursor: 'not-allowed', opacity: 0.5,
            }}>Upload Resume</button>
            {candidate.resume_url && (
              <button disabled title="Coming soon" style={{
                padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                border: '1px solid var(--color-border)', background: 'transparent',
                cursor: 'not-allowed', opacity: 0.5,
              }}>Download</button>
            )}
          </div>
          <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 10 }}>
            Resume upload coming in a future milestone
          </p>
        </div>
      </SectionCard>
    </div>
  )
}

function SectionCard({ title, children }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 14 }}>
        {title}
      </div>
      <div style={{ padding: '16px 20px' }}>{children}</div>
    </div>
  )
}

function InfoGrid({ children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>{children}</div>
}

function InfoItem({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, color: value ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}>{value || '—'}</div>
    </div>
  )
}