export default function Notifications() {
    return (
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>Notifications</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>System alerts and workflow updates</p>
        </div>
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', padding: 48, textAlign: 'center', boxShadow: 'var(--shadow-sm)',
        }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>🔔</div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>No notifications yet</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Workflow completions, approval requests, and system alerts will appear here
          </div>
        </div>
      </div>
    )
  }