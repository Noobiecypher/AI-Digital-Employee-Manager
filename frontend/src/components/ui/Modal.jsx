import { useEffect } from 'react'

export default function Modal({ isOpen, onClose, title, children, width = 520 }) {
  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)',
        width: '100%', maxWidth: width,
        maxHeight: '90vh',
        display: 'flex', flexDirection: 'column',
        boxShadow: 'var(--shadow-lg)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 20px 16px',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
        }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-text-primary)' }}>{title}</h2>
          <button onClick={onClose} style={{
            width: 28, height: 28,
            border: '1px solid var(--color-border)',
            borderRadius: 6,
            background: 'var(--color-bg-elevated)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
            color: 'var(--color-text-secondary)',
          }}>×</button>
        </div>
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
          {children}
        </div>
      </div>
    </div>
  )
}