import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { productsApi } from '../../api/products'
import DataTable from '../../components/ui/DataTable'
import ConfirmDialog from '../../components/ui/ConfirmDialog'
import { useToast } from '../../components/layout/AppLayout'
import { PageHeader, ActionBtn } from '../employees/EmployeeList'
import TagsPopover from '../../components/ui/TagsPopover'

export default function ProductList() {
  const navigate = useNavigate()
  const toast = useToast()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)

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
      await productsApi.delete(deleteTarget.product_name || deleteTarget._id)
      toast.success('Product removed')
      load()
    } catch (err) {
      toast.error('Delete failed', err.message)
    }
  }

  const filtered = products.filter(p =>
    !search ||
    p.product_name?.toLowerCase().includes(search.toLowerCase()) ||
    p.category?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    { key: 'product_name', label: 'Product', render: v => <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{v}</span> },
    { key: 'category', label: 'Category', render: v => v ? <CategoryBadge cat={v} /> : '—' },
    { key: 'price_range', label: 'Price Range' },
    {
      key: 'target_industries', label: 'Industries', render: v => (
        <TagsPopover items={v} color="#06B6D4" bg="rgba(6,182,212,0.12)" border="rgba(6,182,212,0.2)" />
      )
    },
    {
      key: 'description', label: 'Description', render: v => (
        <span style={{ color: 'var(--color-text-secondary)', fontSize: 12.5 }}>
          {v ? (v.length > 60 ? v.slice(0, 60) + '…' : v) : '—'}
        </span>
      )
    },
    {
      key: 'actions', label: '', align: 'right', width: 110,
      render: (_, row) => (
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <ActionBtn onClick={e => { e.stopPropagation(); navigate(`/products/${row.product_name || row._id}/edit`) }}>Edit</ActionBtn>
          <ActionBtn danger onClick={e => { e.stopPropagation(); setDeleteTarget(row) }}>Delete</ActionBtn>
        </div>
      )
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <PageHeader title="Products" count={filtered.length} search={search} onSearch={setSearch} onAdd={() => navigate('/products/new')} addLabel="Add Product" />
      <DataTable columns={columns} data={filtered} loading={loading} emptyMessage="No products found" />
      <ConfirmDialog isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={handleDelete} title="Remove Product" message={`Remove "${deleteTarget?.product_name}"? This cannot be undone.`} />
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

function TagList({ items }) {
  if (!items?.length) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {items.slice(0, 2).map(s => (
        <span key={s} style={{
          padding: '1px 7px', borderRadius: 10, fontSize: 11,
          background: 'rgba(6,182,212,0.12)', color: '#06B6D4',
          border: '1px solid rgba(6,182,212,0.2)', fontWeight: 500,
        }}>{s}</span>
      ))}
      {items.length > 2 && <span style={{ fontSize: 11, color: 'var(--color-text-muted)', alignSelf: 'center' }}>+{items.length - 2}</span>}
    </div>
  )
}