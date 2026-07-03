import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { workflowsApi } from '../../api/workflows'
import DataTable from '../../components/ui/DataTable'
import StatusBadge from '../../components/ui/StatusBadge'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { STATE_META } from '../../constants/workflowStates'
import { useToast } from '../../components/layout/AppLayout'
import { PageHeader } from '../employees/EmployeeList'

export default function WorkflowHistory() {
  const navigate = useNavigate()
  const toast = useToast()
  const [workflows, setWorkflows] = useState([])
  const [loading, setLoading]     = useState(true)
  const [search, setSearch]       = useState('')

  useEffect(() => {
    workflowsApi.getHistory()
      .then(res => {
        // API returns array directly (after fix) or {items:[]}
        const arr = Array.isArray(res) ? res : res?.items || []
        setWorkflows([...arr].reverse())
      })
      .catch(err => toast.error('Failed to load', err.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = workflows.filter(w =>
    !search ||
    w.objective_id?.toLowerCase().includes(search.toLowerCase()) ||
    w.workflow_id?.toLowerCase().includes(search.toLowerCase())
  )

  function getStatus(wf) {
    if (wf.awaiting_human_input) return 'waiting_for_human'
    return wf.status || 'pending'
  }

  const columns = [
    { key: 'objective_id', label: 'Type',
      render: v => <span style={{ fontWeight: 500 }}>{v?.replace(/_/g, ' ')?.replace(/\b\w/g, c => c.toUpperCase()) || '—'}</span>
    },
    { key: 'workflow_id', label: 'Workflow ID',
      render: v => <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>{v}</span>
    },
    { key: 'status', label: 'Status',
      render: (_, row) => {
        const s = getStatus(row)
        const m = STATE_META[s] || {}
        return <StatusBadge label={m.label || s} color={m.color} />
      }
    },
    { key: 'created_at', label: 'Started',
      render: v => v ? new Date(v).toLocaleString() : '—'
    },
    { key: 'view', label: '', align: 'right', width: 80,
      render: (_, row) => (
        <button
          onClick={e => { e.stopPropagation(); navigate(`/workflows/${row.workflow_id}`) }}
          style={{
            padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500,
            border: '1px solid var(--color-border)', background: 'transparent',
            cursor: 'pointer', color: 'var(--color-text-secondary)',
          }}
        >View</button>
      )
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader title="Workflow History" count={filtered.length} search={search} onSearch={setSearch} />
      <DataTable
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage="No workflow history yet"
        onRowClick={row => navigate(`/workflows/${row.workflow_id}`)}
      />
    </div>
  )
}