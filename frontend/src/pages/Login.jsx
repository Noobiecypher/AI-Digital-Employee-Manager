import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { useRole } from '../context/RoleContext'

const WORKFLOW_STEPS = [
  { label: 'Generate Job Description', agent: 'Recruitment Agent', time: '2s', color: '#6366F1' },
  { label: 'Identify Required Skills',  agent: 'Recruitment Agent', time: '1s', color: '#6366F1' },
  { label: 'Shortlist Candidates',      agent: 'Recruitment Agent', time: '4s', color: '#06B6D4' },
  { label: 'Schedule Interviews',       agent: 'HR Agent',          time: '2s', color: '#06B6D4' },
  { label: 'Generate Offer',            agent: 'HR Agent',          time: '3s', color: '#10B981' },
  { label: 'Manager Approval',          agent: 'Human',             time: '—',  color: '#F59E0B' },
]

const STATS = [
  { value: '6',    label: 'Workflow Types',   color: '#6366F1' },
  { value: '5',    label: 'Role Permissions', color: '#06B6D4' },
  { value: '100%', label: 'Real-Time Sync',   color: '#10B981' },
  { value: '3+',   label: 'AI Agents',        color: '#8B5CF6' },
]

export default function Login() {
  const navigate = useNavigate()
  const { login } = useRole()

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [showPw, setShowPw]     = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!email || !password) return setError('Please enter your email and password.')
    setLoading(true)
    try {
      const res  = await authApi.login(email, password)
      const user = await authApi.me(res.access_token)
      login(res.access_token, {
        id:       user.user_id,
        username: user.full_name,
        email:    user.email,
        role:     user.role,
      })
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Invalid email or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      width: '100vw', height: '100vh',
      background: '#090E1A',
      display: 'flex',
      fontFamily: 'Inter, system-ui, sans-serif',
      overflow: 'hidden',
    }}>
      <style>{`
        @keyframes floatY  { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        @keyframes drift   { 0%{transform:translate(0,0)} 50%{transform:translate(20px,-15px)} 100%{transform:translate(0,0)} }
        @keyframes pulse   { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes spin    { to { transform: rotate(360deg) } }
        .login-input {
          width: 100%; padding: 12px 14px; border-radius: 9px; font-size: 13.5px;
          border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.025);
          color: #F1F5F9; outline: none; transition: border-color 0.2s, box-shadow 0.2s;
          font-family: inherit; box-sizing: border-box;
        }
        .login-input::placeholder { color: #334155; }
        .login-input:focus { border-color: #6366F1; box-shadow: 0 0 0 3px rgba(99,102,241,0.15); }
      `}</style>

      {/* ── LEFT PANEL — clean professional login ── */}
      <div style={{
        width: 420, flexShrink: 0,
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        padding: '48px 52px',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        background: '#090E1A',
        position: 'relative', zIndex: 2,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 44 }}>
          <div style={{
            width: 34, height: 34,
            background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
            borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 700, color: '#fff',
            boxShadow: '0 0 16px rgba(99,102,241,0.4)',
          }}>AI</div>
          <span style={{ fontSize: 13.5, fontWeight: 600, color: '#F1F5F9' }}>AI Digital Employee</span>
        </div>

        <h1 style={{ fontSize: 26, fontWeight: 700, color: '#F1F5F9', marginBottom: 6, letterSpacing: '-0.02em' }}>
          Welcome back
        </h1>
        <p style={{ fontSize: 13.5, color: '#64748B', marginBottom: 36 }}>
          Sign in to access your dashboard
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Email */}
          <div>
            <label style={{ fontSize: 11.5, fontWeight: 600, color: '#94A3B8', display: 'block', marginBottom: 7, letterSpacing: '0.03em', textTransform: 'uppercase' }}>
              Email address
            </label>
            <input
              className="login-input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
              autoFocus
            />
          </div>

          {/* Password */}
          <div>
            <label style={{ fontSize: 11.5, fontWeight: 600, color: '#94A3B8', display: 'block', marginBottom: 7, letterSpacing: '0.03em', textTransform: 'uppercase' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                className="login-input"
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowPw(s => !s)}
                tabIndex={-1}
                style={{
                  position: 'absolute', right: 13, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#475569', padding: 2, display: 'flex', alignItems: 'center',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.color = '#94A3B8'}
                onMouseLeave={e => e.currentTarget.style.color = '#475569'}
              >
                {showPw ? (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                )}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              fontSize: 13, color: '#FCA5A5', padding: '10px 13px',
              background: 'rgba(239,68,68,0.08)', borderRadius: 9,
              border: '1px solid rgba(239,68,68,0.2)',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2.5" style={{ flexShrink: 0, marginTop: 1 }}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '12px', borderRadius: 10, fontSize: 14, fontWeight: 600,
              border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
              background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
              color: '#fff', opacity: loading ? 0.7 : 1,
              boxShadow: '0 4px 20px rgba(99,102,241,0.35)',
              marginTop: 4, transition: 'transform 0.15s',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.transform = 'translateY(-1px)' }}
            onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
          >
            {loading && (
              <span style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite', display: 'inline-block' }} />
            )}
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>

      {/* ── RIGHT PANEL — unchanged from original ── */}
      <div style={{
        flex: 1,
        position: 'relative',
        background: 'linear-gradient(155deg, #0D1326 0%, #0a1020 40%, #090E1A 100%)',
        overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* Glow orbs */}
        <div style={{ position: 'absolute', top: '-5%',  right: '10%',  width: 600, height: 600, background: 'radial-gradient(circle, rgba(99,102,241,0.2), transparent 65%)', borderRadius: '50%', filter: 'blur(70px)', animation: 'drift 16s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', bottom: '-10%', left: '5%', width: 500, height: 500, background: 'radial-gradient(circle, rgba(6,182,212,0.16), transparent 65%)', borderRadius: '50%', filter: 'blur(70px)', animation: 'drift 20s ease-in-out infinite reverse' }} />
        <div style={{ position: 'absolute', top: '30%',  right: '30%',  width: 350, height: 350, background: 'radial-gradient(circle, rgba(139,92,246,0.12), transparent 65%)', borderRadius: '50%', filter: 'blur(60px)', animation: 'drift 18s ease-in-out infinite' }} />

        {/* Grid */}
        <div style={{
          position: 'absolute', inset: 0, opacity: 0.35,
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '52px 52px',
          maskImage: 'radial-gradient(ellipse 85% 65% at 40% 35%, black, transparent)',
        }} />

        {/* Main content */}
        <div style={{
          position: 'relative', zIndex: 1, flex: 1,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '48px 80px',
        }}>
          <div style={{ width: '100%', maxWidth: 900, display: 'flex', flexDirection: 'column', gap: 40 }}>

            <div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '5px 13px', borderRadius: 20,
                background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.25)',
                fontSize: 11.5, fontWeight: 600, color: '#818CF8',
                marginBottom: 18, letterSpacing: '0.02em',
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#818CF8', animation: 'pulse 1.8s infinite' }} />
                Powered by AI Agents
              </div>
              <h2 style={{ fontSize: 40, fontWeight: 700, color: '#F1F5F9', lineHeight: 1.12, marginBottom: 14, letterSpacing: '-0.025em' }}>
                One platform.<br />Every HR workflow.
              </h2>
              <p style={{ fontSize: 15, color: '#94A3B8', lineHeight: 1.65, maxWidth: 520 }}>
                From hiring to onboarding to performance reviews — specialized AI agents handle the heavy lifting while you stay in control.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {/* Workflow card */}
              <div style={{
                background: 'rgba(15,22,41,0.75)', backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 18, padding: '22px 24px',
                boxShadow: '0 24px 64px rgba(0,0,0,0.45)',
                animation: 'floatY 6s ease-in-out infinite',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9', marginBottom: 2 }}>hire_employee</div>
                    <div style={{ fontSize: 11, color: '#475569' }}>6 tasks · 12s total</div>
                  </div>
                  <span style={{
                    display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 500, color: '#10B981',
                    padding: '3px 9px', borderRadius: 20, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)',
                  }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor' }} />
                    Completed
                  </span>
                </div>
                {WORKFLOW_STEPS.map((step, i, arr) => (
                  <div key={step.label} style={{ display: 'flex', gap: 12 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                      <div style={{
                        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                        background: `${step.color}20`, border: `1.5px solid ${step.color}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 9, color: step.color, fontWeight: 700,
                      }}>✓</div>
                      {i < arr.length - 1 && <div style={{ width: 1.5, flex: 1, background: `${step.color}30`, minHeight: 14 }} />}
                    </div>
                    <div style={{ flex: 1, paddingBottom: i < arr.length - 1 ? 12 : 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 12.5, color: '#CBD5E1' }}>{step.label}</span>
                        <span style={{ fontSize: 10.5, color: '#475569', marginLeft: 8, flexShrink: 0 }}>{step.time}</span>
                      </div>
                      <div style={{ fontSize: 11, color: '#475569', marginTop: 1 }}>{step.agent}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Right column: stats + features */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  {STATS.map(stat => (
                    <div key={stat.label} style={{
                      background: 'rgba(15,22,41,0.6)', border: '1px solid rgba(255,255,255,0.07)',
                      borderRadius: 14, padding: '16px 18px', position: 'relative', overflow: 'hidden',
                    }}>
                      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${stat.color}, transparent)` }} />
                      <div style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', marginBottom: 3, letterSpacing: '-0.02em' }}>{stat.value}</div>
                      <div style={{ fontSize: 11, color: '#64748B' }}>{stat.label}</div>
                    </div>
                  ))}
                </div>
                {[
                  { title: 'Automated Recruitment', desc: 'AI agents handle shortlisting and offers end-to-end.', icon: '👥', color: '#6366F1' },
                  { title: 'Real-Time Workflows',   desc: 'Track every agent task live from posting to approval.', icon: '⚡', color: '#06B6D4' },
                  { title: 'Role-Based Access',     desc: '5 roles — Admin, Manager, HR, Employee, Candidate.', icon: '🔐', color: '#10B981' },
                ].map(f => (
                  <div key={f.title} style={{
                    display: 'flex', gap: 14, alignItems: 'flex-start',
                    background: 'rgba(15,22,41,0.4)', border: '1px solid rgba(255,255,255,0.05)',
                    borderRadius: 12, padding: '14px 16px',
                  }}>
                    <div style={{
                      width: 34, height: 34, borderRadius: 9, flexShrink: 0,
                      background: `${f.color}18`, border: `1px solid ${f.color}30`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
                    }}>{f.icon}</div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9', marginBottom: 3 }}>{f.title}</div>
                      <div style={{ fontSize: 12, color: '#64748B', lineHeight: 1.5 }}>{f.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div style={{
          position: 'relative', zIndex: 1,
          borderTop: '1px solid rgba(255,255,255,0.05)',
          padding: '16px 80px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'rgba(9,14,26,0.5)',
        }}>
          <span style={{ fontSize: 12, color: '#334155' }}>© 2025 AI Digital Employee Platform · BITS Pilani</span>
          <div style={{ display: 'flex', gap: 20 }}>
            {['Admin', 'Manager', 'HR', 'Employee', 'Candidate'].map(role => (
              <span key={role} style={{ fontSize: 11.5, color: '#334155' }}>{role}</span>
            ))}
          </div>
          <span style={{ fontSize: 12, color: '#334155' }}>v1.0.0</span>
        </div>
      </div>
    </div>
  )
}