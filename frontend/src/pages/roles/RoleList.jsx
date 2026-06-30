import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { rolesApi } from '../../api/roles'
import DataTable from '../../components/ui/DataTable'
import ConfirmDialog from '../../components/ui/ConfirmDialog'
import { useToast } from '../../components/layout/AppLayout'
import { PageHeader, ActionBtn } from '../employees/EmployeeList'
import TagsPopover from '../../components/ui/TagsPopover'

export default function RoleList() {
  const navigate = useNavigate()
  const toast = useToast()
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = async () => {
    try {
      const res = await rolesApi.getAll()
      const arr = Array.isArray(res) ? res : res?.items || res?.roles || []
      setRoles(arr)
    } catch (err) {
      toast.error('Failed to load', err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async () => {
    try {
      await rolesApi.delete(deleteTarget.role || deleteTarget._id)
      toast.success('Role removed')
      load()
    } catch (err) {
      toast.error('Delete failed', err.message)
    }
  }

  const filtered = roles.filter(r =>
    !search ||
    r.role?.toLowerCase().includes(search.toLowerCase()) ||
    r.department?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    { key: 'role', label: 'Role', render: v => <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{v}</span> },
    { key: 'department', label: 'Department' },
    { key: 'experience_years', label: 'Min Exp', render: v => v ? `${v} yrs` : '—' },
    { key: 'location', label: 'Location' },
    { key: 'salary_range', label: 'Salary Range' },
    {
      key: 'skills_required', label: 'Skills', render: v => (
        <TagsPopover items={v} color="#10B981" bg="rgba(16,185,129,0.12)" border="rgba(16,185,129,0.2)" />
      )
    },
    {
      key: 'actions', label: '', align: 'right', width: 100,
      render: (_, row) => (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <ActionBtn onClick={e => { e.stopPropagation(); navigate(`/roles/${encodeURIComponent(row.role || row._id)}/edit`) }}>Edit</ActionBtn>
          <ActionBtn danger onClick={e => { e.stopPropagation(); setDeleteTarget(row) }}>Delete</ActionBtn>
        </div>
      )
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader title="Roles" count={filtered.length} search={search} onSearch={setSearch} onAdd={() => navigate('/roles/new')} addLabel="Add Role" />
      <DataTable columns={columns} data={filtered} loading={loading} emptyMessage="No roles found" />
      <ConfirmDialog isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={handleDelete} title="Remove Role" message={`Remove the "${deleteTarget?.role}" role? This cannot be undone.`} />
    </div>
  )
}

function SkillPills({ skills }) {
  if (!skills?.length) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {skills.slice(0, 3).map(s => (
        <span key={s} style={{
          padding: '1px 7px', borderRadius: 10, fontSize: 11,
          background: 'rgba(16,185,129,0.12)', color: '#10B981',
          border: '1px solid rgba(16,185,129,0.2)', fontWeight: 500,
        }}>{s}</span>
      ))}
      {skills.length > 3 && <span style={{ fontSize: 11, color: 'var(--color-text-muted)', alignSelf: 'center' }}>+{skills.length - 3}</span>}
    </div>
  )
}