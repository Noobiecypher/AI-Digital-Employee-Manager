import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom' 
import { candidatesApi } from '../../api/candidates'
import DataTable from '../../components/ui/DataTable'
import ConfirmDialog from '../../components/ui/ConfirmDialog'
import { useToast } from '../../components/layout/AppLayout'
import { PageHeader, ActionBtn } from '../employees/EmployeeList'
import TagsPopover from '../../components/ui/TagsPopover'

export default function CandidateList() {
  const navigate = useNavigate()
  const toast = useToast()
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = async () => {
    try {
      const res = await candidatesApi.getAll()
      const arr = Array.isArray(res) ? res : res?.items || res?.candidates || []
      setCandidates(arr)
    } catch (err) {
      toast.error('Failed to load', err.message)
    } finally {
      setLoading(false)
    }
  }

  const location = useLocation()
  useEffect(() => { load() }, [location.key])

  const handleDelete = async () => {
    try {
      await candidatesApi.delete(deleteTarget._id || deleteTarget.candidate_id)
      toast.success('Candidate removed')
      load()
    } catch (err) {
      toast.error('Delete failed', err.message)
    }
  }

  const filtered = candidates.filter(c =>
    !search ||
    c.name?.toLowerCase().includes(search.toLowerCase()) ||
    c.role_applied?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    { key: 'name', label: 'Name', render: v => <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{v}</span> },
    { key: 'role_applied', label: 'Role Applied' },
    { key: 'experience_years', label: 'Experience', render: v => v ? `${v} yrs` : '—' },
    { key: 'match_score', label: 'Match Score', render: v => <MatchScore score={v} /> },
    {
      key: 'skills', label: 'Skills', render: v => (
        <TagsPopover items={v} color="#818CF8" bg="rgba(99,102,241,0.12)" border="rgba(99,102,241,0.2)" />
      )
    },
    { key: 'email', label: 'Email' },
    {
      key: 'actions', label: '', align: 'right', width: 140,
      render: (_, row) => (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <ActionBtn onClick={e => { e.stopPropagation(); navigate(`/candidates/${row._id || row.candidate_id}`) }}>View</ActionBtn>
          <ActionBtn onClick={e => { e.stopPropagation(); navigate(`/candidates/${row._id || row.candidate_id}/edit`) }}>Edit</ActionBtn>
          <ActionBtn danger onClick={e => { e.stopPropagation(); setDeleteTarget(row) }}>Delete</ActionBtn>
        </div>
      )
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader title="Candidates" count={filtered.length} search={search} onSearch={setSearch} onAdd={() => navigate('/candidates/new')} addLabel="Add Candidate" />
      <DataTable columns={columns} data={filtered} loading={loading} emptyMessage="No candidates found" />
      <ConfirmDialog isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={handleDelete} title="Remove Candidate" message={`Remove ${deleteTarget?.name} from the pipeline? This cannot be undone.`} />
    </div>
  )
}

function MatchScore({ score }) {
  if (!score && score !== 0) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const pct = Math.min(100, Math.round(score))
  const color = pct >= 70 ? '#10B981' : pct >= 40 ? '#F59E0B' : '#EF4444'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 60, height: 4, background: 'var(--color-border)', borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 12, color, fontWeight: 600, minWidth: 30 }}>{pct}%</span>
    </div>
  )
}

function SkillsList({ skills }) {
  if (!skills?.length) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const show = skills.slice(0, 3)
  const rest = skills.length - 3
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {show.map(s => (
        <span key={s} style={{
          padding: '1px 7px', borderRadius: 10, fontSize: 11,
          background: 'rgba(99,102,241,0.12)', color: '#818CF8',
          border: '1px solid rgba(99,102,241,0.2)', fontWeight: 500,
        }}>{s}</span>
      ))}
      {rest > 0 && <span style={{ fontSize: 11, color: 'var(--color-text-muted)', alignSelf: 'center' }}>+{rest}</span>}
    </div>
  )
}