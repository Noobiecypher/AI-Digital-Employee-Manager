import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { useRole } from '../context/RoleContext'

const MOCK_USERS = {
  admin:     { username: 'admin',     password: 'admin123',    user: { id: '1', username: 'admin',     email: 'admin@company.com',     role: 'admin' } },
  manager:   { username: 'manager',   password: 'manager123',  user: { id: '2', username: 'manager',   email: 'manager@company.com',   role: 'manager' } },
  hr:        { username: 'hr',        password: 'hr123',       user: { id: '3', username: 'hr',        email: 'hr@company.com',        role: 'hr' } },
  employee:  { username: 'employee',  password: 'employee123', user: { id: '4', username: 'employee',  email: 'employee@company.com',  role: 'employee' } },
  candidate: { username: 'candidate', password: 'candidate123',user: { id: '5', username: 'candidate', email: 'candidate@company.com', role: 'candidate' } },
}

const TABS = ['Sign In', 'Sign Up', 'Password recovery']

export default function Login() {
  const navigate = useNavigate()
  const { login } = useRole()
  const [tab, setTab] = useState('Sign In')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [agree, setAgree] = useState(true)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!username || !password) return setError('Enter username and password')
    if (!agree) return setError('Please accept the Terms of use')

    setLoading(true)
    try {
      const res = await authApi.login(username, password)
      login(res.access_token, res.user)
      navigate('/dashboard')
    } catch (err) {
      const mock = Object.values(MOCK_USERS).find(
        m => m.username === username && m.password === password
      )
      if (mock) {
        login('mock_token_' + mock.user.role, mock.user)
        navigate('/dashboard')
      } else {
        setError(err.message || 'Invalid credentials')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleMockLogin = (role) => {
    const mock = MOCK_USERS[role]
    login('mock_token_' + role, mock.user)
    navigate('/dashboard')
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#090E1A',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Inter, system-ui, sans-serif', padding: '32px',
      position: 'relative', overflow: 'hidden',
    }}>
      <style>{`
        @keyframes floatY { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        @keyframes drift { 0% { transform: translate(0,0); } 50% { transform: translate(20px,-15px); } 100% { transform: translate(0,0); } }
        @keyframes pulseDot { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes arrowUp { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
      `}</style>

      {/* Ambient background glow, matches existing palette */}
      <div style={{
        position: 'absolute', top: '-10%', right: '-6%', width: 560, height: 560,
        background: 'radial-gradient(circle, rgba(99,102,241,0.22), transparent 70%)',
        borderRadius: '50%', filter: 'blur(70px)', animation: 'drift 16s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', bottom: '-12%', left: '-8%', width: 460, height: 460,
        background: 'radial-gradient(circle, rgba(6,182,212,0.16), transparent 70%)',
        borderRadius: '50%', filter: 'blur(70px)', animation: 'drift 20s ease-in-out infinite reverse',
      }} />
      <div style={{
        position: 'absolute', inset: 0, opacity: 0.35,
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)',
        backgroundSize: '48px 48px',
        maskImage: 'radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent)',
      }} />

      {/* Outer shell — mirrors the rounded "card on canvas" framing of the reference */}
      <div style={{
        position: 'relative', zIndex: 1,
        width: '100%', maxWidth: 1180,
        background: 'rgba(15,22,41,0.55)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 28,
        display: 'flex',
        boxShadow: '0 30px 90px rgba(0,0,0,0.45)',
        overflow: 'hidden',
      }}>

        {/* Left — sign-in card, raised above the shell like the reference */}
        <div style={{
          flex: '0 0 420px', margin: '32px', display: 'flex', flexDirection: 'column',
          background: 'rgba(9,14,26,0.85)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 18,
          boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
          overflow: 'hidden',
        }}>
          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
            {TABS.map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  flex: 1, padding: '15px 10px', fontSize: 12.5, fontWeight: 600,
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  color: tab === t ? '#F1F5F9' : '#475569',
                  borderBottom: tab === t ? '2px solid #6366F1' : '2px solid transparent',
                  transition: 'color 0.15s',
                }}
              >
                {t}
              </button>
            ))}
          </div>

          <div style={{ padding: '28px 28px 30px' }}>
            {/* Wordmark */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 22 }}>
              <div style={{
                width: 28, height: 28,
                background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
                borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, color: '#fff',
                boxShadow: '0 0 14px rgba(99,102,241,0.4)',
              }}>AI</div>
              <span style={{ fontSize: 12.5, fontWeight: 600, color: '#94A3B8', letterSpacing: '0.01em' }}>
                AI DIGITAL EMPLOYEE
              </span>
            </div>

            <div style={{
              display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24,
            }}>
              <h1 style={{ fontSize: 21, fontWeight: 700, color: '#F1F5F9', letterSpacing: '-0.01em', whiteSpace: 'nowrap' }}>
                {tab}
              </h1>
              <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
            </div>

            {tab === 'Sign In' && (
              <>
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div>
                    <label style={labelStyle}>Login / Email</label>
                    <div style={fieldWrapStyle}>
                      <span style={iconStyle}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>
                      </span>
                      <input
                        value={username}
                        onChange={e => setUsername(e.target.value)}
                        placeholder="you@company.com"
                        style={inputStyle}
                        onFocus={e => { e.target.parentElement.style.borderColor = '#6366F1'; e.target.parentElement.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.15)' }}
                        onBlur={e => { e.target.parentElement.style.borderColor = 'rgba(255,255,255,0.08)'; e.target.parentElement.style.boxShadow = 'none' }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={labelStyle}>Password</label>
                    <div style={fieldWrapStyle}>
                      <span style={iconStyle}>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
                      </span>
                      <input
                        type="password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="••••••••"
                        style={inputStyle}
                        onFocus={e => { e.target.parentElement.style.borderColor = '#6366F1'; e.target.parentElement.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.15)' }}
                        onBlur={e => { e.target.parentElement.style.borderColor = 'rgba(255,255,255,0.08)'; e.target.parentElement.style.boxShadow = 'none' }}
                      />
                    </div>
                  </div>

                  {error && (
                    <div style={{
                      fontSize: 12.5, color: '#EF4444', padding: '9px 13px',
                      background: 'rgba(239,68,68,0.08)', borderRadius: 9,
                      border: '1px solid rgba(239,68,68,0.2)',
                    }}>{error}</div>
                  )}

                  <label style={{
                    display: 'flex', alignItems: 'flex-start', gap: 9, cursor: 'pointer',
                    fontSize: 12, color: '#94A3B8', lineHeight: 1.5, marginTop: 2,
                  }}>
                    <input
                      type="checkbox"
                      checked={agree}
                      onChange={e => setAgree(e.target.checked)}
                      style={{ marginTop: 2, accentColor: '#6366F1', width: 14, height: 14, flexShrink: 0 }}
                    />
                    I agree to the AI Digital Employee{' '}
                    <span style={{ color: '#818CF8', textDecoration: 'underline' }}>Terms of use</span>
                  </label>

                  <button
                    type="submit"
                    disabled={loading}
                    style={{
                      padding: '12.5px', borderRadius: 11, fontSize: 13.5, fontWeight: 600,
                      border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
                      background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
                      color: '#fff', opacity: loading ? 0.7 : 1,
                      boxShadow: '0 4px 22px rgba(99,102,241,0.35)',
                      marginTop: 4, transition: 'transform 0.15s',
                    }}
                    onMouseEnter={e => { if (!loading) e.currentTarget.style.transform = 'translateY(-1px)' }}
                    onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
                  >
                    {loading ? 'Signing in...' : 'Sign In'}
                  </button>
                </form>

                <div style={{ marginTop: 26 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
                    <span style={{ fontSize: 10, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', whiteSpace: 'nowrap' }}>
                      Quick Test Login
                    </span>
                    <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'center' }}>
                    {Object.keys(MOCK_USERS).map(role => (
                      <button
                        key={role}
                        onClick={() => handleMockLogin(role)}
                        style={{
                          padding: '6px 14px', borderRadius: 20, fontSize: 11.5, fontWeight: 500,
                          border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)',
                          color: '#94A3B8', cursor: 'pointer', textTransform: 'capitalize',
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.12)'; e.currentTarget.style.color = '#818CF8'; e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)' }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; e.currentTarget.style.color = '#94A3B8'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}

            {tab === 'Sign Up' && (
              <div style={{ fontSize: 13, color: '#64748B', lineHeight: 1.6, padding: '20px 0' }}>
                Account creation is managed by your workspace admin. Reach out to HR to get provisioned.
              </div>
            )}

            {tab === 'Password recovery' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <label style={labelStyle}>Login / Email</label>
                  <div style={fieldWrapStyle}>
                    <span style={iconStyle}>
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>
                    </span>
                    <input placeholder="you@company.com" style={inputStyle} />
                  </div>
                </div>
                <button style={{
                  padding: '12.5px', borderRadius: 11, fontSize: 13.5, fontWeight: 600,
                  border: 'none', cursor: 'pointer',
                  background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
                  color: '#fff', boxShadow: '0 4px 22px rgba(99,102,241,0.35)',
                }}>
                  Send recovery link
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right — welcome showcase, mirrors the reference's headline + uplift visual */}
        <div style={{
          flex: 1, position: 'relative',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '40px 48px', minHeight: 560,
        }}>
          <div style={{
            position: 'absolute', top: '20%', right: '10%', width: 260, height: 260,
            background: 'radial-gradient(circle, rgba(139,92,246,0.16), transparent 70%)',
            borderRadius: '50%', filter: 'blur(50px)', animation: 'drift 14s ease-in-out infinite',
          }} />

          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'linear-gradient(135deg, #6366F1, #06B6D4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, fontWeight: 700, color: '#fff',
            boxShadow: '0 0 30px rgba(99,102,241,0.45)',
            marginBottom: 22, animation: 'floatY 6s ease-in-out infinite',
          }}>AI</div>

          <h2 style={{
            fontSize: 30, fontWeight: 700, color: '#F1F5F9', textAlign: 'center',
            lineHeight: 1.25, letterSpacing: '-0.02em', marginBottom: 36, maxWidth: 460,
          }}>
            Welcome to the AI Digital<br />Employee platform
          </h2>

          {/* Uplift visual — stands in for the reference's chart + arrow scene, in the existing palette */}
          <div style={{ position: 'relative', width: '100%', maxWidth: 440 }}>
            <svg viewBox="0 0 440 200" width="100%" style={{ display: 'block', animation: 'arrowUp 5s ease-in-out infinite' }}>
              <defs>
                <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#06B6D4" />
                  <stop offset="100%" stopColor="#6366F1" />
                </linearGradient>
              </defs>
              <polyline
                points="10,150 70,120 130,160 190,90 250,110 310,55 370,70 430,20"
                fill="none" stroke="url(#lineGrad)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"
              />
              {[ [10,150], [130,160], [250,110], [370,70], [430,20] ].map(([x,y], i) => (
                <circle key={i} cx={x} cy={y} r="5" fill="#0F1629" stroke="#818CF8" strokeWidth="2.5" />
              ))}
            </svg>
          </div>

          <div style={{ display: 'flex', gap: 28, marginTop: 36 }}>
            {[
              { value: '5',    label: 'Workflow Types' },
              { value: '5',    label: 'Role Permissions' },
              { value: '100%', label: 'Real-Time Sync' },
            ].map((stat, i, arr) => (
              <div key={stat.label} style={{
                textAlign: 'center',
                paddingRight: i < arr.length - 1 ? 28 : 0,
                borderRight: i < arr.length - 1 ? '1px solid rgba(255,255,255,0.08)' : 'none',
              }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', letterSpacing: '-0.02em' }}>{stat.value}</div>
                <div style={{ fontSize: 11, color: '#64748B', marginTop: 2 }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

const labelStyle = {
  fontSize: 11.5, fontWeight: 600, color: '#94A3B8', display: 'block', marginBottom: 7,
  textTransform: 'uppercase', letterSpacing: '0.03em',
}

const fieldWrapStyle = {
  display: 'flex', alignItems: 'center', gap: 9,
  border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10,
  background: 'rgba(255,255,255,0.025)', padding: '0 13px',
  transition: 'all 0.15s',
}

const iconStyle = { color: '#64748B', display: 'flex', flexShrink: 0 }

const inputStyle = {
  flex: 1, padding: '12px 0', fontSize: 13.5, border: 'none', outline: 'none',
  background: 'transparent', color: '#F1F5F9', boxSizing: 'border-box',
}