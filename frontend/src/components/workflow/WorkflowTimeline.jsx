import { useState } from 'react'

export default function WorkflowTimeline({ taskOutputs = [] }) {
  // API returns task_outputs as an array of {task_id, output, ...}
  // But handle both array and object shapes defensively
  const entries = Array.isArray(taskOutputs)
    ? taskOutputs.map(t => [t.task_id || t.id, t.output ?? t])
    : Object.entries(taskOutputs)

  if (entries.length === 0) {
    return (
      <div style={{ color: 'var(--color-text-muted)', fontSize: 13, padding: '16px 0' }}>
        No task outputs available yet.
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {entries.map(([taskId, output], i) => (
        <TimelineStep
          key={taskId}
          taskId={taskId}
          output={output}
          index={i}
          isLast={i === entries.length - 1}
        />
      ))}
    </div>
  )
}

function TimelineStep({ taskId, output, index, isLast }) {
  const [expanded, setExpanded] = useState(false)
  const content = typeof output === 'string' ? output : JSON.stringify(output, null, 2)

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      {/* Timeline line + dot */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: 'var(--color-primary-light)',
          border: '2px solid var(--color-primary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 600, color: 'var(--color-primary)',
          flexShrink: 0,
        }}>
          {index + 1}
        </div>
        {!isLast && (
          <div style={{ width: 2, flex: 1, background: 'var(--color-border)', minHeight: 16, margin: '4px 0' }} />
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, paddingBottom: isLast ? 0 : 16 }}>
        <div
          onClick={() => setExpanded(e => !e)}
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: expanded ? 'var(--radius-md) var(--radius-md) 0 0' : 'var(--radius-md)',
            padding: '10px 14px',
            cursor: 'pointer',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}
        >
          <span style={{ fontWeight: 500, fontSize: 13, color: 'var(--color-text-primary)' }}>
            {String(taskId).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {expanded ? '▲ Hide' : '▼ View'}
          </span>
        </div>
        {expanded && (
          <div style={{
            background: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border)',
            borderTop: 'none',
            borderRadius: '0 0 var(--radius-md) var(--radius-md)',
            padding: '12px 14px',
          }}>
            <pre style={{
              fontSize: 12.5, lineHeight: 1.6,
              color: 'var(--color-text-secondary)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              margin: 0,
              fontFamily: 'ui-monospace, monospace',
            }}>
              {content}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}