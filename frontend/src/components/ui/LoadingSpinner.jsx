export default function LoadingSpinner({ size = 24, color = 'var(--color-primary)' }) {
    return (
      <div style={{
        width: size, height: size,
        border: `2px solid var(--color-border)`,
        borderTop: `2px solid ${color}`,
        borderRadius: '50%',
        animation: 'spin 0.7s linear infinite',
      }}>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }
  
  export function PageLoader() {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        minHeight: 300, flexDirection: 'column', gap: 12,
      }}>
        <LoadingSpinner size={32} />
        <span style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>Loading...</span>
      </div>
    )
  }