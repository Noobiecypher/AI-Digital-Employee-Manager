import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { productsApi } from '../../api/products'
import { useToast } from '../../components/layout/AppLayout'
import { FormCard, Field, Input, Textarea, FormActions } from '../_shared/FormComponents'

export default function ProductForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const isEdit = Boolean(id)

  const [form, setForm] = useState({
    product_name: '', description: '', category: '',
    price_range: '', pain_points: '', target_industries: '',
  })
  const [loading, setLoading]   = useState(false)
  const [fetching, setFetching] = useState(isEdit)

  useEffect(() => {
    if (!isEdit) return
    productsApi.getOne(id)
      .then(data => setForm({
        ...data,
        pain_points:        (data.pain_points || []).join(', '),
        target_industries:  (data.target_industries || []).join(', '),
      }))
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setFetching(false))
  }, [id])

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.product_name) return toast.warning('Required', 'Product name is required')
    setLoading(true)
    try {
      const payload = {
        ...form,
        pain_points:       form.pain_points ? form.pain_points.split(',').map(s => s.trim()).filter(Boolean) : [],
        target_industries: form.target_industries ? form.target_industries.split(',').map(s => s.trim()).filter(Boolean) : [],
      }
      if (isEdit) {
        await productsApi.update(id, payload)
        toast.success('Product updated')
      } else {
        await productsApi.create(payload)
        toast.success('Product created')
      }
      navigate('/products')
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Loading...</div>

  return (
    <FormCard title={isEdit ? 'Edit Product' : 'Add Product'} onBack={() => navigate('/products')}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Field label="Product Name *">
          <Input value={form.product_name} onChange={set('product_name')} placeholder="AI Recruiter Pro" />
        </Field>
        <Field label="Category">
          <Input value={form.category} onChange={set('category')} placeholder="HR Tech" />
        </Field>
        <Field label="Price Range">
          <Input value={form.price_range} onChange={set('price_range')} placeholder="₹10,000 – ₹50,000 / mo" />
        </Field>
        <Field label="Target Industries (comma-separated)">
          <Input value={form.target_industries} onChange={set('target_industries')} placeholder="BFSI, Healthcare, Retail" />
        </Field>
        <Field label="Description" span={2}>
          <Textarea value={form.description} onChange={set('description')} placeholder="Brief description of the product..." rows={3} />
        </Field>
        <Field label="Pain Points (comma-separated)" span={2}>
          <Textarea value={form.pain_points} onChange={set('pain_points')} placeholder="Manual hiring, slow onboarding, high attrition..." rows={2} />
        </Field>
      </div>
      <FormActions onCancel={() => navigate('/products')} onSubmit={handleSubmit} loading={loading} isEdit={isEdit} />
    </FormCard>
  )
}