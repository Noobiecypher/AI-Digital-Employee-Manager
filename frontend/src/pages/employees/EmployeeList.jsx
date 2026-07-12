import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { employeesApi } from '../../api/employees'
import { goalsApi } from '../../api/goals'
import DataTable from '../../components/ui/DataTable'
import ConfirmDialog from '../../components/ui/ConfirmDialog'
import { useToast } from '../../components/layout/AppLayout'

export default function EmployeeList() {
  const navigate = useNavigate()
  const toast = useToast()
  const [employees, setEmployees]       = useState([])
  const [loading, setLoading]           = useState(true)
  const [search, setSearch]             = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [allGoals, setAllGoals]         = useState([])
  const [goalsDropdown, setGoalsDropdown] = useState(null) // { employeeId, name, goals[] }

  const load = async () => {
    try {
      const [empRes, goalsRes] = await Promise.all([
        employeesApi.getAll(),
        goalsApi.getAll().catch(() => ({ items: [] })),
      ])
      const arr = Array.isArray(empRes) ? empRes : empRes?.items || empRes?.employees || []
      setEmployees(arr)
      setAllGoals(Array.isArray(goalsRes) ? goalsRes : goalsRes?.items || [])
    } catch (err) {
      toast.error('Failed to load', err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async () => {
    try {
      await employeesApi.delete(deleteTarget._id || deleteTarget.employee_id)
      toast.success('Employee removed')
      load()
    } catch (err) {
      toast.error('Delete failed', err.message)
    }
  }

  const getEmployeeGoals = (name) =>
    allGoals.filter(g => g.employee_name?.toLowerCase() === name?.toLowerCase())

  const filtered = employees.filter(e =>
    !search ||
    e.employee_name?.toLowerCase().includes(search.toLowerCase()) ||
    e.role?.toLowerCase().includes(search.toLowerCase()) ||
    e.department?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    { key: 'employee_id',   label: 'ID', width: 100 },
    { key: 'employee_name', label: 'Name',
      render: v => <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{v}</span> },
    { key: 'role',        label: 'Role' },
    { key: 'department',  label: 'Department' },
    { key: 'work_mode',   label: 'Work Mode', render: v => <WorkModeBadge mode={v} /> },
    { key: 'manager_name', label: 'Manager' },
    { key: 'actions', label: '', align: 'right', width: 180,
      render: (_, row) => {
        const empGoals = getEmployeeGoals(row.employee_name)
        return (
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
            {empGoals.length > 0 ? (
              <div style={{ position: 'relative' }}>
                <select
                  onClick={e => e.stopPropagation()}
                  onChange={e => {
                    if (!e.target.value) return
                    const [name, period] = e.target.value.split('|||')
                    navigate(`/goals/${encodeURIComponent(name)}/${encodeURIComponent(period)}`)
                    e.target.value = ''
                  }}
                  style={{
                    padding: '4px 8px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                    border: '1px solid rgba(99,102,241,0.3)',
                    background: 'rgba(99,102,241,0.1)', color: '#818CF8',
                    cursor: 'pointer', outline: 'none',
                  }}
                  defaultValue=""
                >
                  <option value="" disabled>Goals ▾</option>
                  {empGoals.map(g => (
                    <option key={g.review_period} value={`${g.employee_name}|||${g.review_period}`}>
                      {g.review_period} — {g.goals_achieved?.length || 0}/{g.goals_set?.length || 0} done
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <span style={{ fontSize: 11.5, color: 'var(--color-text-muted)' }}>No goals</span>
            )}
            <ActionBtn onClick={e => { e.stopPropagation(); navigate(`/employees/${row._id || row.employee_id}/edit`) }}>Edit</ActionBtn>
            <ActionBtn danger onClick={e => { e.stopPropagation(); setDeleteTarget(row) }}>Delete</ActionBtn>
          </div>
        )
      }
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader
        title="Employees" count={filtered.length}
        search={search} onSearch={setSearch}
        onAdd={() => navigate('/employees/new')} addLabel="Add Employee"
      />
      <DataTable columns={columns} data={filtered} loading={loading} emptyMessage="No employees found" />
      <ConfirmDialog
        isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={handleDelete}
        title="Remove Employee"
        message={`Are you sure you want to remove ${deleteTarget?.employee_name}? This action cannot be undone.`}
      />
    </div>
  )
}

function WorkModeBadge({ mode }) {
  const map = {
    hybrid: { bg: 'rgba(99,102,241,0.12)',  color: '#818CF8', border: 'rgba(99,102,241,0.2)'  },
    remote: { bg: 'rgba(16,185,129,0.12)',  color: '#10B981', border: 'rgba(16,185,129,0.2)'  },
    onsite: { bg: 'rgba(245,158,11,0.12)',  color: '#F59E0B', border: 'rgba(245,158,11,0.2)'  },
  }
  const s = map[mode?.toLowerCase()] || { bg: 'rgba(255,255,255,0.06)', color: '#94A3B8', border: 'rgba(255,255,255,0.1)' }
  return (
    <span style={{ padding: '2px 9px', borderRadius: 12, fontSize: 12, fontWeight: 500,
      textTransform: 'capitalize', background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
      {mode || '—'}
    </span>
  )
}

export function PageHeader({ title, count, search, onSearch, onAdd, addLabel }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <div style={{ flex: 1 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>{title}</h2>
        {count != null && (
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
            {count} record{count !== 1 ? 's' : ''}
          </p>
        )}
      </div>
      {onSearch && (
        <input type="search" placeholder="Search..." value={search} onChange={e => onSearch(e.target.value)} style={{
          padding: '8px 12px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
          color: 'var(--color-text-primary)', outline: 'none', width: 220,
        }} />
      )}
      {onAdd && (
        <button onClick={onAdd} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
          background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
          color: '#fff', border: 'none', cursor: 'pointer',
          boxShadow: '0 0 14px rgba(99,102,241,0.25)',
        }}>+ {addLabel}</button>
      )}
    </div>
  )
}

export function ActionBtn({ onClick, danger, children }) {
  return (
    <button onClick={onClick} style={{
      padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500,
      cursor: 'pointer', border: '1px solid',
      borderColor: danger ? 'rgba(239,68,68,0.3)'  : 'var(--color-border)',
      background:  danger ? 'rgba(239,68,68,0.12)' : 'transparent',
      color:       danger ? '#EF4444'               : 'var(--color-text-secondary)',
    }}>{children}</button>
  )
}