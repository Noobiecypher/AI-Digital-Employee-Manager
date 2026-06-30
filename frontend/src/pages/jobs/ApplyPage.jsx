import { useState } from 'react'
import { useParams } from 'react-router-dom'

const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB
const ALLOWED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
const ALLOWED_EXT   = ['.pdf', '.docx']

export default function ApplyPage() {
  const { job_id } = useParams()
  const [form, setForm] = useState({ name: '', email: '', phone: '' })
  const [file, setFile]           = useState(null)
  const [fileError, setFileError] = useState('')
  const [errors, setErrors]       = useState({})
  const [loading, setLoading]     = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [dragOver, setDragOver]   = useState(false)

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const validateFile = (f) => {
    if (!f) return 'Please upload your resume'
    if (f.size > MAX_FILE_SIZE) return 'File must be under 5MB'
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXT.includes(ext)) return 'Only PDF and DOCX files are accepted'
    return ''
  }

  const handleFile = (f) => {
    const err = validateFile(f)
    setFileError(err)
    if (!err) setFile(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const validate = () => {
    const errs = {}
    if (!form.name.trim())  errs.name  = 'Name is required'
    if (!form.email.trim()) errs.email = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(form.email)) errs.email = 'Enter a valid email'
    if (!form.phone.trim()) errs.phone = 'Phone is required'
    const fe = validateFile(file)
    if (fe) errs.file = fe
    return errs
  }

  const handleSubmit = async () => {
    const errs = validate()
    setErrors(errs)
    if (Object.keys(errs).length > 0) return

    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('name',   form.name)
      formData.append('email',  form.email)
      formData.append('phone',  form.phone)
      formData.append('job_id', job_id || '')
      formData.append('resume', file)

      // POST to backend when endpoint is ready
      // await fetch(`${import.meta.env.VITE_API_URL}/apply`, { method: 'POST', body: formData })

      // Simulate success for now
      await new Promise(r => setTimeout(r, 1200))
      setSubmitted(true)
    } catch (err) {
      setErrors({ submit: 'Submission failed. Please try again.' })
    } finally {
      setLoading(false)
    }
  }

  if (submitted) return <SuccessScreen name={form.name} />

  return (
    <div style={{
      minHeight: '100vh', background: '#090E1A',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24, fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <div style={{ width: '100%', maxWidth: 520 }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 44, height: 44, margin: '0 auto 16px',
            background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
            borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 700, color: '#fff',
            boxShadow: '0 0 24px rgba(99,102,241,0.4)',
          }}>AI</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', marginBottom: 6 }}>Apply for this Role</h1>
          {job_id && (
            <div style={{ fontSize: 12, color: '#475569', fontFamily: 'monospace' }}>Job ID: {job_id}</div>
          )}
        </div>

        {/* Form card */}
        <div style={{
          background: '#0F1629', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 16, padding: '28px 32px',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <FormField label="Full Name *" error={errors.name}>
              <input
                value={form.name} onChange={set('name')}
                placeholder="Ananya Rao"
                style={inputStyle(errors.name)}
                onFocus={e => e.target.style.borderColor = '#6366F1'}
                onBlur={e => e.target.style.borderColor = errors.name ? '#EF4444' : 'rgba(255,255,255,0.08)'}
              />
            </FormField>

            <FormField label="Email Address *" error={errors.email}>
              <input
                type="email" value={form.email} onChange={set('email')}
                placeholder="ananya@email.com"
                style={inputStyle(errors.email)}
                onFocus={e => e.target.style.borderColor = '#6366F1'}
                onBlur={e => e.target.style.borderColor = errors.email ? '#EF4444' : 'rgba(255,255,255,0.08)'}
              />
            </FormField>

            <FormField label="Phone Number *" error={errors.phone}>
              <input
                value={form.phone} onChange={set('phone')}
                placeholder="+91 98765 43210"
                style={inputStyle(errors.phone)}
                onFocus={e => e.target.style.borderColor = '#6366F1'}
                onBlur={e => e.target.style.borderColor = errors.phone ? '#EF4444' : 'rgba(255,255,255,0.08)'}
              />
            </FormField>

            {/* File upload */}
            <FormField label="Resume *" error={errors.file || fileError}>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById('resume-input').click()}
                style={{
                  border: `2px dashed ${dragOver ? '#6366F1' : (errors.file || fileError) ? '#EF4444' : 'rgba(255,255,255,0.1)'}`,
                  borderRadius: 10, padding: '24px 16px',
                  textAlign: 'center', cursor: 'pointer',
                  background: dragOver ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.02)',
                  transition: 'all 0.15s',
                }}
              >
                <input
                  id="resume-input" type="file"
                  accept=".pdf,.docx"
                  style={{ display: 'none' }}
                  onChange={e => handleFile(e.target.files[0])}
                />
                {file ? (
                  <div>
                    <div style={{ fontSize: 24, marginBottom: 6 }}>📄</div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#818CF8' }}>{file.name}</div>
                    <div style={{ fontSize: 11.5, color: '#475569', marginTop: 3 }}>
                      {(file.size / 1024 / 1024).toFixed(2)} MB · Click to change
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 24, marginBottom: 8 }}>📁</div>
                    <div style={{ fontSize: 13, color: '#94A3B8', marginBottom: 4 }}>
                      Drag & drop or <span style={{ color: '#818CF8', fontWeight: 500 }}>browse</span>
                    </div>
                    <div style={{ fontSize: 11.5, color: '#475569' }}>PDF or DOCX · Max 5MB</div>
                  </div>
                )}
              </div>
            </FormField>

            {errors.submit && (
              <div style={{ fontSize: 13, color: '#EF4444', textAlign: 'center', padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.2)' }}>
                {errors.submit}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              style={{
                width: '100%', padding: '12px', borderRadius: 10, fontSize: 14, fontWeight: 600,
                border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
                background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
                color: '#fff', opacity: loading ? 0.7 : 1,
                boxShadow: '0 0 20px rgba(99,102,241,0.3)',
                transition: 'all 0.15s', marginTop: 4,
              }}
            >
              {loading ? 'Submitting...' : 'Submit Application'}
            </button>

            <div style={{ fontSize: 11.5, color: '#475569', textAlign: 'center' }}>
              By submitting, you agree to our terms of use and privacy policy.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function SuccessScreen({ name }) {
  return (
    <div style={{
      minHeight: '100vh', background: '#090E1A',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <div style={{ textAlign: 'center', maxWidth: 400, padding: 24 }}>
        <div style={{
          width: 64, height: 64, margin: '0 auto 20px',
          background: 'rgba(16,185,129,0.15)',
          border: '2px solid rgba(16,185,129,0.4)',
          borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28,
        }}>✓</div>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', marginBottom: 10 }}>Application Submitted!</h2>
        <p style={{ fontSize: 14, color: '#94A3B8', lineHeight: 1.6, marginBottom: 24 }}>
          Thank you, {name}. We've received your application and will be in touch if you're shortlisted.
        </p>
        <div style={{
          background: '#0F1629', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12, padding: '14px 18px',
          fontSize: 13, color: '#64748B',
        }}>
          You can close this window now.
        </div>
      </div>
    </div>
  )
}

function FormField({ label, error, children }) {
  return (
    <div>
      <label style={{ fontSize: 12.5, fontWeight: 600, color: '#94A3B8', letterSpacing: '0.02em', display: 'block', marginBottom: 6 }}>
        {label}
      </label>
      {children}
      {error && <div style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>{error}</div>}
    </div>
  )
}

function inputStyle(hasError) {
  return {
    width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13.5,
    border: `1px solid ${hasError ? '#EF4444' : 'rgba(255,255,255,0.08)'}`,
    background: 'rgba(255,255,255,0.03)', color: '#F1F5F9',
    outline: 'none', boxSizing: 'border-box', transition: 'border-color 0.15s',
  }
}