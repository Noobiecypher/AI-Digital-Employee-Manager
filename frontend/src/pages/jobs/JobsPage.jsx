import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { workflowsApi } from '../../api/workflows'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

// Extract job postings from workflow task_outputs
async function fetchJobs() {
  const res  = await workflowsApi.getAll()
  const wfs  = Array.isArray(res) ? res : res?.items || []
  const jobs = []

  for (const wf of wfs) {
    if (wf.objective_id !== 'hire_employee') continue
    try {
      const detail = await workflowsApi.getOne(wf.workflow_id || wf._id)
      const t1 = detail.task_outputs?.find(t => t.task_id === 't1')
      if (!t1?.output) continue
      const out = t1.output
      jobs.push({
        job_id:       out.job_id || wf.workflow_id,
        workflow_id:  wf.workflow_id || wf._id,
        title:        'Backend Engineer',
        description:  out.job_description || '',
        embed_script: out.embed_script || '',
        status:       wf.status || 'completed',
        created_at:   wf.created_at,
        applicants:   detail.task_outputs?.find(t => t.task_id === 't3')?.output?.shortlisted_candidates?.length || 0,
      })
    } catch {}
  }
  return jobs
}

export default function JobsPage() {
  const navigate                = useNavigate()
  const toast                   = useToast()
  const { job_id }              = useParams()
  const [jobs, setJobs]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)
  const [copied, setCopied]     = useState(false)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    fetchJobs()
      .then(data => {
        setJobs(data)
        if (job_id) setSelected(data.find(j => j.job_id === job_id) || null)
        else if (data.length > 0) setSelected(data[0])
      })
      .catch(err => toast.error('Failed to load jobs', err.message))
      .finally(() => setLoading(false))
  }, [])

  const handleCopy = () => {
    if (!selected?.embed_script) return
    navigator.clipboard.writeText(selected.embed_script).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleStartShortlisting = async () => {
    if (!selected) return
    setStarting(true)
    try {
      const res = await workflowsApi.start({
        objective_id: 'hire_employee',
        params: {
          role:       selected.title || 'Backend Engineer',
          department: 'Engineering',
          job_type:   'full-time',
        },
      })
      const id = res.workflow_id || res.id
      toast.success('Workflow started', 'Shortlisting workflow is now running')
      if (id) navigate(`/workflows/${id}`)
    } catch (err) {
      toast.error('Failed to start', err.message)
    } finally {
      setStarting(false)
    }
  }

  if (loading) return <PageLoader />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Job Postings</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{jobs.length} active posting{jobs.length !== 1 ? 's' : ''}</p>
        </div>
        <button onClick={() => navigate('/workflows/start')} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
          color: '#fff', border: 'none', cursor: 'pointer',
          boxShadow: '0 0 14px rgba(99,102,241,0.25)',
        }}>+ New Hire Workflow</button>
      </div>

      {jobs.length === 0 ? (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 56, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>💼</div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: 14, marginBottom: 16 }}>
            No job postings yet. Start a Hire Employee workflow to generate one.
          </div>
          <button onClick={() => navigate('/workflows/start')} style={{
            padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
            background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
            color: '#fff', border: 'none', cursor: 'pointer',
          }}>Start Hire Workflow</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20, alignItems: 'start' }}>
          {/* Job list */}
          <div style={{
            background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>
              Postings
            </div>
            {jobs.map((job, i) => (
              <div
                key={job.job_id}
                onClick={() => setSelected(job)}
                style={{
                  padding: '12px 16px',
                  borderBottom: i < jobs.length - 1 ? '1px solid var(--color-border)' : 'none',
                  cursor: 'pointer',
                  borderLeft: `3px solid ${selected?.job_id === job.job_id ? '#6366F1' : 'transparent'}`,
                  background: selected?.job_id === job.job_id ? 'rgba(99,102,241,0.08)' : 'transparent',
                  transition: 'all 0.1s',
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: 3 }}>
                  {job.title || 'Job Posting'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                  {job.job_id}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3 }}>
                  {job.created_at ? new Date(job.created_at).toLocaleDateString() : '—'} · {job.applicants} applicants
                </div>
              </div>
            ))}
          </div>

          {/* Job detail */}
          {selected && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Header */}
              <div style={{
                background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-lg)', padding: '20px 24px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 4 }}>
                      {selected.title || 'Job Posting'}
                    </h3>
                    <div style={{ fontSize: 12, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                      ID: {selected.job_id}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => navigate(`/apply/${selected.job_id}`)}
                      style={{
                        padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                        border: '1px solid rgba(6,182,212,0.3)', background: 'rgba(6,182,212,0.1)',
                        color: '#06B6D4', cursor: 'pointer',
                      }}
                    >
                      Preview Apply Page
                    </button>
                    <button
                      onClick={() => navigate(`/workflows/${selected.workflow_id}`)}
                      style={{
                        padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                        border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
                        color: 'var(--color-text-secondary)', cursor: 'pointer',
                      }}
                    >
                      View Workflow →
                    </button>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <Stat label="Applicants" value={selected.applicants} />
                  <Stat label="Status"     value={selected.status} />
                  <Stat label="Created"    value={selected.created_at ? new Date(selected.created_at).toLocaleDateString() : '—'} />
                </div>
              </div>

              {/* Embed script */}
              {selected.embed_script && (
                <div style={{
                  background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-lg)', overflow: 'hidden',
                }}>
                  <div style={{
                    padding: '12px 18px', borderBottom: '1px solid var(--color-border)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <div>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>Embed Script</span>
                      <span style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginLeft: 8 }}>
                        Paste this on your careers page
                      </span>
                    </div>
                    <button
                      onClick={handleCopy}
                      style={{
                        padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 500,
                        border: `1px solid ${copied ? 'rgba(16,185,129,0.3)' : 'var(--color-border)'}`,
                        background: copied ? 'rgba(16,185,129,0.12)' : 'var(--color-bg-elevated)',
                        color: copied ? '#10B981' : 'var(--color-text-secondary)',
                        cursor: 'pointer', transition: 'all 0.2s',
                      }}
                    >
                      {copied ? '✓ Copied!' : 'Copy to Clipboard'}
                    </button>
                  </div>
                  <div style={{ padding: '16px 18px' }}>
                    <pre style={{
                      background: 'rgba(0,0,0,0.3)', borderRadius: 8, padding: '14px 16px',
                      fontSize: 12.5, color: '#06B6D4', fontFamily: 'ui-monospace, monospace',
                      whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0,
                      border: '1px solid rgba(6,182,212,0.15)',
                    }}>
                      {selected.embed_script}
                    </pre>
                  </div>
                </div>
              )}

              {/* Job description preview */}
              {selected.description && (
                <div style={{
                  background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-lg)', overflow: 'hidden',
                }}>
                  <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13 }}>
                    Job Description
                  </div>
                  <div style={{ padding: '16px 18px', maxHeight: 300, overflowY: 'auto' }}>
                    <pre style={{
                      fontSize: 13, lineHeight: 1.7, color: 'var(--color-text-secondary)',
                      whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, fontFamily: 'inherit',
                    }}>
                      {selected.description}
                    </pre>
                  </div>
                </div>
              )}

              {/* Close & Shortlist */}
              <div style={{
                background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)',
                borderRadius: 'var(--radius-lg)', padding: '16px 20px',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, color: '#F59E0B', marginBottom: 3 }}>
                    Close Applications & Run Shortlisting
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                    Currently {selected.applicants} applicant{selected.applicants !== 1 ? 's' : ''}. Starts a new hire_employee workflow to shortlist candidates.
                  </div>
                </div>
                <button
                  onClick={handleStartShortlisting}
                  disabled={starting}
                  style={{
                    padding: '8px 16px', borderRadius: 8, fontSize: 12.5, fontWeight: 500,
                    border: '1px solid rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.15)',
                    color: '#F59E0B', cursor: starting ? 'not-allowed' : 'pointer',
                    opacity: starting ? 0.6 : 1, transition: 'all 0.15s',
                  }}
                >
                  {starting ? 'Starting...' : 'Close & Shortlist'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', textTransform: 'capitalize' }}>{value || '—'}</div>
    </div>
  )
}