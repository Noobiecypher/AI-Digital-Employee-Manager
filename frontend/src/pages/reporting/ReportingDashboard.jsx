import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { reportsApi } from '../../api/reports'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'

export default function ReportingDashboard() {
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    reportsApi.getAnalytics()
      .then(setData)
      .catch(err => toast.error('Failed to load analytics', err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageLoader />

  const stats     = data?.statistics  || {}
  const agents    = data?.agent_usage || []
  const dist      = data?.objective_distribution || {}
  const history   = data?.workflow_execution_history || data?.charts || []
  const narrative = data?.narrative_summary || data?.narrative || null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Analytics</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>Live data from MongoDB</p>
        </div>
        <button onClick={() => navigate('/reporting/reports')} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          border: '1px solid var(--color-border)',
          background: 'var(--color-bg-elevated)',
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
        }}>View Reports →</button>
      </div>

      {/* AI summary disclaimer */}
      {narrative && (
        <div style={{
          background: 'rgba(245,158,11,0.08)',
          border: '1px solid rgba(245,158,11,0.2)',
          borderRadius: 'var(--radius-lg)', padding: '14px 18px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#F59E0B' }}>⚠ AI-generated narrative summary</span>
            <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>May not reflect exact metrics</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.6, margin: 0 }}>
            {narrative}
          </p>
        </div>
      )}

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 14 }}>
        <MetricCard label="Total Workflows"   value={stats.total_workflows  ?? data?.total_workflows  ?? '—'} color="#6366F1" />
        <MetricCard label="Completed"         value={stats.completed        ?? data?.completed        ?? '—'} color="#10B981" />
        <MetricCard label="Failed"            value={stats.failed           ?? data?.failed           ?? '—'} color="#EF4444" />
        <MetricCard label="Running"           value={stats.running          ?? data?.running          ?? '—'} color="#06B6D4" />
        <MetricCard label="Awaiting Approval" value={stats.paused           ?? data?.paused           ?? '—'} color="#F59E0B" />
        <MetricCard label="Success Rate"      value={data?.success_rate != null ? `${Math.round(data.success_rate)}%` : '—'} color="#10B981" />
      </div>

      {/* Distribution + Agent usage */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 16 }}>

        {Object.keys(dist).length > 0 && (
          <div style={{
            background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          }}>
            <div style={{ padding: '13px 18px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13, color: 'var(--color-text-primary)' }}>
              Workflow Distribution
            </div>
            <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {Object.entries(dist).map(([type, count]) => {
                const total = Object.values(dist).reduce((a, b) => a + b, 0)
                const pct   = total > 0 ? Math.round((count / total) * 100) : 0
                return (
                  <div key={type}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--color-text-primary)' }}>
                        {type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{count} ({pct}%)</span>
                    </div>
                    <div style={{ height: 5, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
                      <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #6366F1, #06B6D4)', borderRadius: 3 }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {agents.length > 0 && (
          <div style={{
            background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          }}>
            <div style={{ padding: '13px 18px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13, color: 'var(--color-text-primary)' }}>
              Agent Usage
            </div>
            <div style={{ padding: '8px 0' }}>
              {agents.map((agent, i) => (
                <div key={i} style={{
                  padding: '10px 18px',
                  borderBottom: i < agents.length - 1 ? '1px solid var(--color-border)' : 'none',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', textTransform: 'capitalize' }}>
                    {(agent.assigned_agent || agent.agent || '').replace(/_/g, ' ')}
                  </span>
                  <span style={{
                    padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                    background: 'rgba(99,102,241,0.12)', color: '#818CF8',
                    border: '1px solid rgba(99,102,241,0.2)',
                  }}>
                    {agent.count ?? agent.usage ?? '—'} runs
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Execution history */}
      {history.length > 0 && (
        <div style={{
          background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
          <div style={{ padding: '13px 18px', borderBottom: '1px solid var(--color-border)', fontWeight: 600, fontSize: 13, color: 'var(--color-text-primary)' }}>
            Execution History
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Workflow', 'Status', 'Agent', 'Date'].map(h => (
                    <th key={h} style={{
                      padding: '10px 16px', textAlign: 'left',
                      fontWeight: 600, fontSize: 11,
                      color: 'var(--color-text-muted)',
                      textTransform: 'uppercase', letterSpacing: '0.07em',
                      background: 'var(--color-bg-surface-2)',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 10).map((row, i) => (
                  <tr
                    key={i}
                    style={{ borderBottom: i < Math.min(history.length, 10) - 1 ? '1px solid var(--color-border)' : 'none' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '12px 16px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
                      {(row.workflow_name || row.task_name || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <StatusPill status={row.status} />
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', textTransform: 'capitalize' }}>
                      {(row.assigned_agent || '').replace(/_/g, ' ')}
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                      {row.date || row.created_at ? new Date(row.date || row.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusPill({ status }) {
  const map = {
    completed:         { bg: 'rgba(16,185,129,0.12)',  color: '#10B981', border: 'rgba(16,185,129,0.25)'  },
    failed:            { bg: 'rgba(239,68,68,0.12)',   color: '#EF4444', border: 'rgba(239,68,68,0.25)'   },
    running:           { bg: 'rgba(99,102,241,0.12)',  color: '#818CF8', border: 'rgba(99,102,241,0.25)'  },
    waiting_for_human: { bg: 'rgba(245,158,11,0.12)',  color: '#F59E0B', border: 'rgba(245,158,11,0.25)'  },
    pending:           { bg: 'rgba(255,255,255,0.06)', color: '#94A3B8', border: 'rgba(255,255,255,0.1)'  },
  }
  const s = map[status] || map.pending
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 20, fontSize: 11.5, fontWeight: 500,
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor', flexShrink: 0 }} />
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

function MetricCard({ label, value, color = '#6366F1' }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)', padding: '18px 20px',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${color}, transparent)`,
      }} />
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
    </div>
  )
}