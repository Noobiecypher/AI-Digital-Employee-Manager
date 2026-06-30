const STYLES = {
  success: { background: 'rgba(16,185,129,0.12)',  color: '#10B981', border: '1px solid rgba(16,185,129,0.25)' },
  warning: { background: 'rgba(245,158,11,0.12)',  color: '#F59E0B', border: '1px solid rgba(245,158,11,0.25)' },
  danger:  { background: 'rgba(239,68,68,0.12)',   color: '#EF4444', border: '1px solid rgba(239,68,68,0.25)'  },
  info:    { background: 'rgba(99,102,241,0.12)',  color: '#818CF8', border: '1px solid rgba(99,102,241,0.25)' },
  default: { background: 'rgba(255,255,255,0.06)', color: '#94A3B8', border: '1px solid rgba(255,255,255,0.1)' },
}

export default function StatusBadge({ status, label, color }) {
  const style = STYLES[color] || STYLES[status] || STYLES.default
  return (
    <span style={{
      ...style,
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 20,
      fontSize: 11.5, fontWeight: 500, whiteSpace: 'nowrap',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', flexShrink: 0 }} />
      {label}
    </span>
  )
}