import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, RadialBarChart, RadialBar,
} from 'recharts'
import { employeesApi } from '../api/employees'
import { candidatesApi } from '../api/candidates'
import { workflowsApi } from '../api/workflows'
import { reportsApi } from '../api/reports'
import { PageLoader } from '../components/ui/LoadingSpinner'
import StatusBadge from '../components/ui/StatusBadge'
import { STATE_META } from '../constants/workflowStates'
import { useRole } from '../context/RoleContext'

const CHART_COLORS = ['#6366F1', '#06B6D4', '#10B981', '#F59E0B', '#EF4444']

function StatCard({ label, value, sub, color = '#6366F1' }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)',
      padding: '18px 20px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${color}, transparent)`,
      }} />
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color, lineHeight: 1, marginBottom: 4 }}>
        {value ?? '—'}
      </div>
      {sub && <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)' }}>{sub}</div>}
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)',
      borderRadius: 8, padding: '8px 12px', fontSize: 12,
    }}>
      {label && <div style={{ color: 'var(--color-text-muted)', marginBottom: 4 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || 'var(--color-text-primary)', fontWeight: 500 }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  )
}

function ChartCard({ title, children }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-lg)',
      padding: '16px 18px',
    }}>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 14, letterSpacing: '0.02em' }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function EmptyChart({ message }) {
  return (
    <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)', fontSize: 12 }}>
      {message}
    </div>
  )
}

function EmployeeDashboard({ data }) {
  const navigate = useNavigate()
  const { userName } = useRole()
  const myGoals = data.goals || []
  const firstName = userName.split(' ')[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
      <div style={{
        background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(6,182,212,0.08))',
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 'var(--radius-xl)', padding: '24px 28px',
      }}>
        <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: 'var(--color-text-primary)' }}>
          Good day, {firstName} 👋
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
          Here's a summary of your work. Switch to Manager view to access the full platform.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 14 }}>
        {[
          { label: 'My Goals',      sub: 'View and track your performance goals', to: '/goals',         color: '#6366F1', locked: false },
          { label: 'Notifications', sub: 'Check system alerts and updates',        to: '/notifications', color: '#06B6D4', locked: false },
          { label: 'Team Access',   sub: 'Contact your manager for full access',   to: null,             color: '#475569', locked: true  },
        ].map(card => (
          <div key={card.label} onClick={() => card.to && navigate(card.to)} style={{
            background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)', padding: '20px',
            cursor: card.to ? 'pointer' : 'default',
            position: 'relative', overflow: 'hidden',
            opacity: card.locked ? 0.45 : 1, transition: 'box-shadow 0.15s',
          }}
            onMouseEnter={e => { if (card.to) e.currentTarget.style.boxShadow = 'var(--shadow-md)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none' }}
          >
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${card.color}, transparent)` }} />
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, color: 'var(--color-text-primary)' }}>{card.label}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{card.sub}</div>
            {card.locked && <div style={{ position: 'absolute', top: 12, right: 12, fontSize: 12 }}>🔒</div>}
          </div>
        ))}
      </div>

      <div style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>My Goals</span>
          <button onClick={() => navigate('/goals')} style={{ fontSize: 11.5, color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer' }}>View all →</button>
        </div>
        {myGoals.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>No goals assigned yet</div>
        ) : myGoals.slice(0, 3).map((goal, i) => {
          const goalsList = goal.goals_set || goal.goals || []
          const achieved  = goal.goals_achieved || []
          const pct       = goalsList.length > 0 ? Math.round((achieved.length / goalsList.length) * 100) : 0
          const color     = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444'
          return (
            <div key={i}
              onClick={() => navigate(`/goals/${encodeURIComponent(goal.employee_name)}/${encodeURIComponent(goal.review_period)}`)}
              style={{
                padding: '12px 18px',
                borderBottom: i < Math.min(myGoals.length, 3) - 1 ? '1px solid var(--color-border)' : 'none',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                cursor: 'pointer', transition: 'background 0.1s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{goal.employee_name}</div>
                <div style={{ fontSize: 11.5, color: 'var(--color-text-muted)', marginTop: 1 }}>{goal.review_period}</div>
              </div>
              <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600, background: `${color}18`, color, border: `1px solid ${color}30` }}>
                {achieved.length}/{goalsList.length} done
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { isManager } = useRole()
  const [data, setData] = useState({ employees: [], candidates: [], workflows: [], analytics: null })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      employeesApi.getAll(),
      candidatesApi.getAll(),
      workflowsApi.getAll(),
      reportsApi.getAnalytics(),
    ]).then(([emp, can, wf, an]) => {
      const toArr = (val) => {
        if (!val) return []
        if (Array.isArray(val)) return val
        return val.items || val.employees || val.candidates || val.workflows || val.data || []
      }
      setData({
        employees:  emp.status === 'fulfilled' ? toArr(emp.value) : [],
        candidates: can.status === 'fulfilled' ? toArr(can.value) : [],
        workflows:  wf.status  === 'fulfilled' ? toArr(wf.value)  : [],
        analytics:  an.status  === 'fulfilled' ? an.value : null,
      })
      setLoading(false)
    })
  }, [])

  if (loading) return <PageLoader />
  if (!isManager) return <EmployeeDashboard data={data} />

  const pending   = data.workflows.filter(w => w.awaiting_human_input === true)
  const running   = data.workflows.filter(w => w.status === 'running' || w.state === 'running')
  const recent    = [...data.workflows].reverse().slice(0, 5)
  const analytics = data.analytics || {}

  const donutData = [
    { name: 'Completed', value: analytics.completed || 0 },
    { name: 'Running',   value: analytics.running   || 0 },
    { name: 'Pending',   value: analytics.paused    || 0 },
    { name: 'Failed',    value: analytics.failed    || 0 },
  ].filter(d => d.value > 0)

  const lineData = (analytics.workflow_execution_history || analytics.charts || [])
    .slice(-7)
    .map((h, i) => ({
      day: h.date ? new Date(h.date).toLocaleDateString('en', { month: 'short', day: 'numeric' }) : `Day ${i + 1}`,
      workflows: 1,
    }))
    .reduce((acc, cur) => {
      const existing = acc.find(a => a.day === cur.day)
      if (existing) { existing.workflows++; return acc }
      return [...acc, { ...cur, workflows: 1 }]
    }, [])

  const agentData = (analytics.agent_usage || []).map(a => ({
    name: (a.assigned_agent || a.agent || '').replace(/_/g, ' '),
    runs: a.count || a.usage || 0,
  }))

  const candidateScoreData = data.candidates.map(c => ({
    name: c.name?.split(' ')[0] || 'Unknown',
    score: Math.round(c.match_score || 0),
  }))

  const successRate = Math.round(analytics.success_rate || 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%', boxSizing: 'border-box' }}>

      {pending.length > 0 && (
        <div onClick={() => navigate('/approvals')} style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 'var(--radius-lg)', padding: '12px 18px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#F59E0B', boxShadow: '0 0 6px #F59E0B' }} />
            <span style={{ fontWeight: 500, color: '#F59E0B', fontSize: 13 }}>
              {pending.length} workflow{pending.length > 1 ? 's' : ''} waiting for approval
            </span>
          </div>
          <span style={{ fontSize: 12, color: '#F59E0B', opacity: 0.8 }}>Review →</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 14 }}>
        <StatCard label="Total Employees" value={data.employees.length}  sub="Active headcount"    color="#6366F1" />
        <StatCard label="Candidates"      value={data.candidates.length} sub="In pipeline"         color="#06B6D4" />
        <StatCard label="Workflows Run"   value={analytics.total_workflows ?? data.workflows.length} sub="All time" color="#8B5CF6" />
        <StatCard label="Success Rate"    value={`${successRate}%`}      sub="Completed workflows" color="#10B981" />
        <StatCard label="Needs Approval"  value={pending.length}         sub="Pending review"      color="#F59E0B" />
        <StatCard label="Running Now"     value={running.length}         sub="In progress"         color="#06B6D4" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) minmax(0,1fr)', gap: 14 }}>
        <ChartCard title="Workflow Activity">
          {lineData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="day" tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="workflows" stroke="#6366F1" strokeWidth={2} dot={{ fill: '#6366F1', r: 3 }} activeDot={{ r: 5 }} name="Workflows" />
              </LineChart>
            </ResponsiveContainer>
          ) : <EmptyChart message="No activity data yet" />}
        </ChartCard>

        <ChartCard title="Workflow Status">
          {donutData.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={donutData} cx="50%" cy="50%" innerRadius={50} outerRadius={70} paddingAngle={3} dataKey="value">
                    {donutData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 12px', justifyContent: 'center' }}>
                {donutData.map((d, i) => (
                  <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: CHART_COLORS[i] }} />
                    <span style={{ color: 'var(--color-text-secondary)' }}>{d.name}</span>
                    <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : <EmptyChart message="No workflow data yet" />}
        </ChartCard>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)', gap: 14 }}>
        <ChartCard title="Agent Usage">
          {agentData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={agentData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#475569', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={false} tickLine={false} width={70} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="runs" fill="#6366F1" radius={[0, 4, 4, 0]} name="Runs" />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart message="No agent data yet" />}
        </ChartCard>

        <ChartCard title="Candidate Match Scores">
          {candidateScoreData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={candidateScoreData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="score" radius={[4, 4, 0, 0]} name="Match %">
                  {candidateScoreData.map((entry, i) => (
                    <Cell key={i} fill={entry.score >= 70 ? '#10B981' : entry.score >= 40 ? '#F59E0B' : '#EF4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart message="No candidates yet" />}
        </ChartCard>

        <ChartCard title="Success Rate">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <div style={{ position: 'relative', width: '100%', height: 110 }}>
              <ResponsiveContainer width="100%" height={110}>
                <RadialBarChart cx="50%" cy="90%" innerRadius="120%" outerRadius="150%" startAngle={180} endAngle={0}
                  data={[{ value: successRate, fill: successRate >= 70 ? '#10B981' : successRate >= 40 ? '#F59E0B' : '#EF4444' }]}
                >
                  <RadialBar dataKey="value" cornerRadius={6} background={{ fill: 'rgba(255,255,255,0.04)' }} max={100} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div style={{ position: 'absolute', bottom: 8, left: '50%', transform: 'translateX(-50%)', textAlign: 'center', pointerEvents: 'none' }}>
                <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1, color: successRate >= 70 ? '#10B981' : successRate >= 40 ? '#F59E0B' : '#EF4444' }}>
                  {successRate}%
                </div>
                <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 3 }}>success rate</div>
              </div>
            </div>
            <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 7, marginTop: 4 }}>
              {[
                { label: 'Completed', value: analytics.completed || 0, color: '#10B981' },
                { label: 'Failed',    value: analytics.failed    || 0, color: '#EF4444' },
                { label: 'Running',   value: analytics.running   || 0, color: '#6366F1' },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.color, boxShadow: `0 0 4px ${s.color}` }} />
                    <span style={{ color: 'var(--color-text-secondary)' }}>{s.label}</span>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: s.color }}>{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,3fr) minmax(0,2fr)', gap: 14 }}>
        <div style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>Recent Workflows</span>
            <button onClick={() => navigate('/workflows/history')} style={{ fontSize: 11.5, color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer' }}>
              View all →
            </button>
          </div>
          {recent.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>No workflows yet</div>
          ) : recent.map((wf, i) => {
            const id     = wf.workflow_id || wf._id || wf.id
            const type   = wf.objective_id || wf.workflow_type || ''
            const status = wf.status || wf.state || ''
            const meta   = STATE_META[status] || {}
            return (
              <div key={id || i} onClick={() => navigate(`/workflows/${id}`)}
                style={{ padding: '11px 18px', borderBottom: i < recent.length - 1 ? '1px solid var(--color-border)' : 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', transition: 'background 0.1s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>
                    {type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Workflow'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 1, fontFamily: 'monospace' }}>{id}</div>
                </div>
                <StatusBadge
                  label={wf.awaiting_human_input ? 'Needs Approval' : (meta.label || status)}
                  color={wf.awaiting_human_input ? 'warning' : meta.color}
                />
              </div>
            )
          })}
        </div>

        <div style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--color-border)' }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>Quick Actions</span>
          </div>
          <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 7 }}>
            {[
              { label: 'Start a Workflow', to: '/workflows/start', primary: true },
              { label: 'Add Employee',     to: '/employees/new' },
              { label: 'Add Candidate',    to: '/candidates/new' },
              { label: 'Review Approvals', to: '/approvals' },
              { label: 'View Reports',     to: '/reporting' },
            ].map(action => (
              <button key={action.to} onClick={() => navigate(action.to)} style={{
                padding: '9px 14px', borderRadius: 8, fontSize: 12.5, fontWeight: 500,
                textAlign: 'left', cursor: 'pointer',
                border: action.primary ? 'none' : '1px solid var(--color-border)',
                background: action.primary ? 'linear-gradient(135deg, #6366F1, #4F46E5)' : 'transparent',
                color: action.primary ? '#fff' : 'var(--color-text-secondary)',
                transition: 'all 0.15s',
                boxShadow: action.primary ? '0 0 16px rgba(99,102,241,0.25)' : 'none',
              }}
                onMouseEnter={e => { if (!action.primary) { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--color-text-primary)' }}}
                onMouseLeave={e => { if (!action.primary) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-text-secondary)' }}}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}