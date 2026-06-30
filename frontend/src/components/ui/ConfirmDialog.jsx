import Modal from './Modal'

export default function ConfirmDialog({ isOpen, onClose, onConfirm, title, message, confirmLabel = 'Delete', isDangerous = true }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} width={400}>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
        {message}
      </p>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button onClick={onClose} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          border: '1px solid var(--color-border)',
          background: 'var(--color-bg-elevated)',
          cursor: 'pointer',
          color: 'var(--color-text-secondary)',
        }}>Cancel</button>
        <button onClick={() => { onConfirm(); onClose() }} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          border: 'none', cursor: 'pointer', color: '#fff',
          background: isDangerous
            ? 'linear-gradient(135deg, #EF4444, #DC2626)'
            : 'linear-gradient(135deg, #6366F1, #4F46E5)',
        }}>{confirmLabel}</button>
      </div>
    </Modal>
  )
}