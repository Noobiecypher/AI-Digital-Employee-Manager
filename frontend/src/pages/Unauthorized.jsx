import { useNavigate } from 'react-router-dom'
import { useRole } from '../context/RoleContext'

export default function Unauthorized() {
  const navigate = useNavigate()
  const { role } = useRole()

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '60vh', gap: 16, textAlign: 'center',
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%',
        background: 'var(--color-danger-bg)',
        border: '1px solid var(--color-danger-border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 24,
      }}>🔒</div>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>Access Restricted</h2>
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', maxWidth: 320 }}>
          This page is only available to managers. You're currently signed in as an <strong>{role}</strong>.
        </p>
      </div>
      <button
        onClick={() => navigate('/dashboard')}
        style={{
          padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          background: 'var(--color-primary)', color: '#fff', border: 'none', cursor: 'pointer',
        }}
      >
        Back to Dashboard
      </button>
    </div>
  )
}