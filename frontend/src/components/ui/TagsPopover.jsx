import { useState, useRef, useEffect } from 'react'

export default function TagsPopover({ items = [], color = '#6366F1', bg = 'rgba(99,102,241,0.12)', border = 'rgba(99,102,241,0.2)', max = 2 }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (!items?.length) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>

  const show = items.slice(0, max)
  const rest = items.slice(max)

  const pillStyle = {
    padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 500,
    background: bg, color, border: `1px solid ${border}`,
    whiteSpace: 'nowrap',
  }

  return (
    <div ref={ref} style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center', position: 'relative' }}>
      {show.map(s => <span key={s} style={pillStyle}>{s}</span>)}
      {rest.length > 0 && (
        <>
          <button
            onClick={e => { e.stopPropagation(); setOpen(o => !o) }}
            style={{
              ...pillStyle,
              cursor: 'pointer', border: `1px solid ${border}`,
              background: open ? bg : 'rgba(255,255,255,0.06)',
              color: open ? color : 'var(--color-text-muted)',
            }}
          >
            +{rest.length}
          </button>
          {open && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, zIndex: 100,
              background: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border)',
              borderRadius: 10, padding: '10px 12px',
              marginTop: 4, minWidth: 160,
              boxShadow: 'var(--shadow-lg)',
              display: 'flex', flexWrap: 'wrap', gap: 6,
            }}>
              {items.map(s => <span key={s} style={pillStyle}>{s}</span>)}
            </div>
          )}
        </>
      )}
    </div>
  )
}