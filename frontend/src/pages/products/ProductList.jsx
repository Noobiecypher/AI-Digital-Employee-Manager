import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { productsApi } from '../../api/products'
import DataTable from '../../components/ui/DataTable'
import ConfirmDialog from '../../components/ui/ConfirmDialog'
import { useToast } from '../../components/layout/AppLayout'
import { PageHeader, ActionBtn } from '../employees/EmployeeList'
import TagsPopover from '../../components/ui/TagsPopover'
import { useRole } from '../../context/RoleContext'

export default function ProductList() {
  const navigate = useNavigate()
  const toast = useToast()
  const { role } = useRole()
  const [products, setProducts] = useState([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

  // Permission gates
  const canCreate = ['admin', 'manager'].includes(role)
  const canEdit   = ['admin', 'manager'].includes(role)
  const canDelete = ['admin'].includes(role)

  const load = async () => {
    try {
      const res = await productsApi.getAll()
      const arr = Array.isArray(res) ? res : res?.items || res?.products || []
      setProducts(arr)
    } catch (err) {
      toast.error('Failed to load', err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async () => {
    try {
      await productsApi.delete(deleteTarget.product_name)
      toast.success('Product removed')
      setDeleteTarget(null)
      load()
    } catch (err) {
      toast.error('Delete failed', err.message)
      setDeleteTarget(null)
    }
  }

  const filtered = products.filter(p =>
    !search ||
    p.product_name?.toLowerCase().includes(search.toLowerCase()) ||
    p.category?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    {
      key: 'product_name', label: 'Product',
      render: v => <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{v}</span>
    },
    {
      key: 'category', label: 'Category',
      render: v => v ? <CategoryBadge cat={v} /> : '—'
    },
    { key: 'price_range', label: 'Price Range' },
    {
      key: 'target_industries', label: 'Industries',
      render: v => (
        <TagsPopover items={v} color="#06B6D4" bg="rgba(6,182,212,0.12)" border="rgba(6,182,212,0.2)" />
      )
    },
    {
      key: 'description', label: 'Description',
      render: v => (
        <span style={{ color: 'var(--color-text-secondary)', fontSize: 12.5 }}>
          {v ? (v.length > 60 ? v.slice(0, 60) + '…' : v) : '—'}
        </span>
      )
    },
    // Only show actions column if user can do something
    ...(canEdit || canDelete ? [{
      key: 'actions', label: '', align: 'right', width: 110,
      render: (_, row) => (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          {canEdit && (
            <ActionBtn onClick={e => { e.stopPropagation(); navigate(`/products/${encodeURIComponent(row.product_name)}/edit`) }}>
              Edit
            </ActionBtn>
          )}
          {canDelete && (
            <ActionBtn danger onClick={e => { e.stopPropagation(); setDeleteTarget(row) }}>
              Delete
            </ActionBtn>
          )}
        </div>
      )
    }] : []),
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader
        title="Products" count={filtered.length}
        search={search} onSearch={setSearch}
        onAdd={canCreate ? () => navigate('/products/new') : null}
        addLabel="Add Product"
      />
      <DataTable
        columns={columns}
        data={filtered}
        loading={loading}
        emptyMessage="No products found"
        onRowClick={row => navigate(`/products/${encodeURIComponent(row.product_name)}`)}
      />
      {canDelete && (
        <ConfirmDialog
          isOpen={!!deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onConfirm={handleDelete}
          title="Remove Product"
          message={`Remove "${deleteTarget?.product_name}"? This cannot be undone.`}
        />
      )}
    </div>
  )
}

function CategoryBadge({ cat }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 10, fontSize: 12, fontWeight: 500,
      background: 'rgba(99,102,241,0.12)', color: '#818CF8',
      border: '1px solid rgba(99,102,241,0.2)',
    }}>{cat}</span>
  )
}