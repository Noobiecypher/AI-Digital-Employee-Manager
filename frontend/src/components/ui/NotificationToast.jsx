const TYPE_STYLE = {
    success: { border: 'var(--color-success-border)', icon: '✓',  iconBg: 'var(--color-success-bg)', iconColor: 'var(--color-success-text)' },
    danger:  { border: 'var(--color-danger-border)',  icon: '✕',  iconBg: 'var(--color-danger-bg)',  iconColor: 'var(--color-danger-text)'  },
    warning: { border: 'var(--color-warning-border)', icon: '!',  iconBg: 'var(--color-warning-bg)', iconColor: 'var(--color-warning-text)' },
    info:    { border: 'var(--color-info-border)',    icon: 'i',  iconBg: 'var(--color-info-bg)',    iconColor: 'var(--color-info-text)'    },
  }
  
  export default function NotificationToast({ toasts, onRemove }) {
    return (
      <div style={{
        position: 'fixed', bottom: 24, right: 24,
        display: 'flex', flexDirection: 'column', gap: 8,
        zIndex: 9999, maxWidth: 360,
      }}>
        {toasts.map(toast => {
          const s = TYPE_STYLE[toast.type] || TYPE_STYLE.info
          return (
            <div key={toast.id} style={{
              background: 'var(--color-bg-surface)',
              border: `1px solid ${s.border}`,
              borderRadius: 'var(--radius-lg)',
              padding: '12px 14px',
              display: 'flex', alignItems: 'flex-start', gap: 10,
              boxShadow: 'var(--shadow-lg)',
              animation: 'slideIn 0.2s ease',
            }}>
              <style>{`@keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`}</style>
              <div style={{
                width: 24, height: 24, borderRadius: 6, flexShrink: 0,
                background: s.iconBg, color: s.iconColor,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: 12,
              }}>{s.icon}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                {toast.title && <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>{toast.title}</div>}
                {toast.message && <div style={{ fontSize: 12.5, color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>{toast.message}</div>}
              </div>
              <button onClick={() => onRemove(toast.id)} style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--color-text-muted)', fontSize: 16, lineHeight: 1,
                padding: 0, flexShrink: 0,
              }}>×</button>
            </div>
          )
        })}
      </div>
    )
  }