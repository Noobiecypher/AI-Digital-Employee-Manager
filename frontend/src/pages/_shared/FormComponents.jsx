// Shared form primitives used across all form pages

export function FormCard({ title, children, onBack }) {
  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        {onBack && (
          <button onClick={onBack} style={{
            padding: '6px 12px', borderRadius: 8, fontSize: 13,
            border: '1px solid var(--color-border)',
            background: 'var(--color-bg-elevated)',
            cursor: 'pointer', color: 'var(--color-text-secondary)',
          }}>← Back</button>
        )}
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>{title}</h2>
      </div>
      <div style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)',
        padding: '28px 32px',
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>
        {children}
      </div>
    </div>
  )
}
  
  export function Field({ label, children, span }) {
    return (
      <div style={{ gridColumn: span === 2 ? 'span 2' : undefined, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-secondary)', letterSpacing: '0.02em' }}>
          {label}
        </label>
        {children}
      </div>
    )
  }
  
  const inputStyle = {
    padding: '9px 12px',
    borderRadius: 8,
    border: '1px solid var(--color-border)',
    background: 'var(--color-bg-elevated)',
    fontSize: 13.5,
    color: 'var(--color-text-primary)',
    width: '100%',
    outline: 'none',
    transition: 'border-color 0.15s',
  }
  
  export function Input({ ...props }) {
    return (
      <input
        style={inputStyle}
        onFocus={e => e.target.style.borderColor = 'var(--color-primary)'}
        onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
        {...props}
      />
    )
  }
  
  export function Select({ children, ...props }) {
    return (
      <select style={{ ...inputStyle, cursor: 'pointer' }} {...props}>
        {children}
      </select>
    )
  }
  
  export function Textarea({ ...props }) {
    return (
      <textarea
        style={{ ...inputStyle, resize: 'vertical', minHeight: 90, lineHeight: 1.5 }}
        onFocus={e => e.target.style.borderColor = 'var(--color-primary)'}
        onBlur={e => e.target.style.borderColor = 'var(--color-border)'}
        {...props}
      />
    )
  }
  
  export function FormActions({ onCancel, onSubmit, loading, isEdit }) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 8, borderTop: '1px solid var(--color-border)', marginTop: 4 }}>
        <button onClick={onCancel} style={{
          padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          border: '1px solid var(--color-border)',
          background: 'var(--color-bg-elevated)',
          cursor: 'pointer',
          color: 'var(--color-text-secondary)',
        }}>Cancel</button>
        <button onClick={onSubmit} disabled={loading} style={{
          padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          border: 'none',
          background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
          color: '#fff',
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.7 : 1,
          minWidth: 100,
        }}>
          {loading ? 'Saving...' : isEdit ? 'Save Changes' : 'Create'}
        </button>
      </div>
    )
  }