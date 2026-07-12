import LoadingSpinner from './LoadingSpinner'

export default function DataTable({ columns, data, loading, emptyMessage = 'No data found', onRowClick }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--color-border)',
      overflow: 'hidden',
    }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              {columns.map(col => (
                <th key={col.key} style={{
                  padding: '11px 16px',
                  textAlign: col.align || 'left',
                  fontWeight: 600,
                  fontSize: 11,
                  color: 'var(--color-text-muted)',
                  letterSpacing: '0.07em',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                  width: col.width,
                  background: 'var(--color-bg-surface-2)',
                }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 40, textAlign: 'center' }}>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <LoadingSpinner />
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
                  {emptyMessage}
                </td>
              </tr>
            ) : data.map((row, i) => (
              <tr
                key={row._id || row.candidate_id || row.employee_id || row.product_id || row.workflow_id || row.role || i}
                onClick={() => onRowClick?.(row)}
                style={{
                  borderBottom: '1px solid var(--color-border)',
                  cursor: onRowClick ? 'pointer' : 'default',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e => { if (onRowClick) e.currentTarget.style.background = 'var(--color-bg-surface-2)' }}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                {columns.map(col => (
                  <td key={col.key} style={{
                    padding: '12px 16px',
                    textAlign: col.align || 'left',
                    color: 'var(--color-text-secondary)',
                    verticalAlign: 'middle',
                  }}>
                    {col.render
                      ? col.render(row[col.key], row)
                      : row[col.key] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}