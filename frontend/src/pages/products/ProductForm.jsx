import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { productsApi } from '../../api/products'
import { useToast } from '../../components/layout/AppLayout'
import { FormCard, Field, Input, Textarea, FormActions } from '../_shared/FormComponents'

// Price points in rupees (monthly)
const PRICE_POINTS = [
  10000, 25000, 50000, 75000,
  100000, 250000, 500000, 750000,
  1000000, 2500000, 5000000, 7500000,
  10000000, 25000000, 50000000, 100000000,
]

function formatPrice(val) {
  if (val >= 10000000) return `₹${(val / 10000000).toFixed(val % 10000000 === 0 ? 0 : 1)}Cr`
  if (val >= 100000)   return `₹${(val / 100000).toFixed(val % 100000 === 0 ? 0 : 1)}L`
  if (val >= 1000)     return `₹${(val / 1000).toFixed(0)}K`
  return `₹${val}`
}

function PriceRangeSlider({ minIdx, maxIdx, onChange }) {
  const min = PRICE_POINTS[minIdx]
  const max = PRICE_POINTS[maxIdx]
  const total = PRICE_POINTS.length - 1

  const minPct = (minIdx / total) * 100
  const maxPct = (maxIdx / total) * 100

  return (
    <div style={{ padding: '4px 0 8px' }}>
      {/* Price display */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 14, fontWeight: 600,
          background: 'rgba(99,102,241,0.12)', color: '#818CF8',
          border: '1px solid rgba(99,102,241,0.25)',
        }}>{formatPrice(min)}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>per month</div>
        <div style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 14, fontWeight: 600,
          background: 'rgba(99,102,241,0.12)', color: '#818CF8',
          border: '1px solid rgba(99,102,241,0.25)',
        }}>{formatPrice(max)}{maxIdx === total ? '+' : ''}</div>
      </div>

      {/* Track */}
      <div style={{ position: 'relative', height: 6, margin: '0 8px' }}>
        {/* Background track */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '100%',
          borderRadius: 3, background: 'rgba(255,255,255,0.08)',
        }} />
        {/* Active range */}
        <div style={{
          position: 'absolute', top: 0, height: '100%', borderRadius: 3,
          left: `${minPct}%`, width: `${maxPct - minPct}%`,
          background: 'linear-gradient(90deg, #6366F1, #818CF8)',
        }} />
        {/* Min thumb */}
        <input
          type="range" min={0} max={total} value={minIdx} step={1}
          onChange={e => {
            const v = Number(e.target.value)
            if (v < maxIdx) onChange(v, maxIdx)
          }}
          style={{
            position: 'absolute', top: '50%', transform: 'translateY(-50%)',
            width: '100%', margin: 0, appearance: 'none', background: 'transparent',
            pointerEvents: 'none', zIndex: 3,
            '--thumb-color': '#6366F1',
          }}
          className="price-thumb"
        />
        {/* Max thumb */}
        <input
          type="range" min={0} max={total} value={maxIdx} step={1}
          onChange={e => {
            const v = Number(e.target.value)
            if (v > minIdx) onChange(minIdx, v)
          }}
          style={{
            position: 'absolute', top: '50%', transform: 'translateY(-50%)',
            width: '100%', margin: 0, appearance: 'none', background: 'transparent',
            pointerEvents: 'none', zIndex: 3,
          }}
          className="price-thumb"
        />
      </div>

      {/* Tick labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, padding: '0 4px' }}>
        {[0, 4, 8, 12, 15].map(i => (
          <span key={i} style={{ fontSize: 10, color: 'var(--color-text-muted)' }}>
            {formatPrice(PRICE_POINTS[i])}{i === 15 ? '+' : ''}
          </span>
        ))}
      </div>

      <style>{`
        .price-thumb { pointer-events: none; }
        .price-thumb::-webkit-slider-thumb {
          appearance: none; pointer-events: all;
          width: 18px; height: 18px; border-radius: 50%;
          background: #6366F1; border: 2px solid #fff;
          box-shadow: 0 0 8px rgba(99,102,241,0.5);
          cursor: pointer; transition: transform 0.1s;
        }
        .price-thumb::-webkit-slider-thumb:hover { transform: scale(1.2); }
        .price-thumb::-moz-range-thumb {
          width: 18px; height: 18px; border-radius: 50%;
          background: #6366F1; border: 2px solid #fff;
          box-shadow: 0 0 8px rgba(99,102,241,0.5);
          cursor: pointer;
        }
      `}</style>
    </div>
  )
}

export default function ProductForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const isEdit = Boolean(id)

  const [form, setForm] = useState({
    product_name: '', description: '', category: '',
    pain_points: '', target_industries: '',
  })
  const [minIdx, setMinIdx] = useState(0)   // ₹10K
  const [maxIdx, setMaxIdx] = useState(15)  // ₹10Cr+
  const [loading, setLoading]   = useState(false)
  const [fetching, setFetching] = useState(isEdit)

  useEffect(() => {
    if (!isEdit) return
    productsApi.getOne(id)
      .then(data => {
        setForm({
          ...data,
          pain_points:       (data.pain_points || []).join(', '),
          target_industries: (data.target_industries || []).join(', '),
        })
        // Try to parse existing price_range back to slider positions
        // e.g. "₹10K – ₹5L / mo" → find closest indices
        if (data.price_range) {
          const parts = data.price_range.replace(/\s*\/\s*mo/i, '').split(/\s*[–-]\s*/)
          if (parts.length === 2) {
            const parse = s => {
              s = s.replace(/[₹,\s]/g, '')
              if (s.endsWith('Cr'))  return parseFloat(s) * 10000000
              if (s.endsWith('L'))   return parseFloat(s) * 100000
              if (s.endsWith('K'))   return parseFloat(s) * 1000
              return parseFloat(s) || 0
            }
            const lo = parse(parts[0])
            const hi = parse(parts[1])
            const loIdx = PRICE_POINTS.reduce((best, p, i) => Math.abs(p - lo) < Math.abs(PRICE_POINTS[best] - lo) ? i : best, 0)
            const hiIdx = PRICE_POINTS.reduce((best, p, i) => Math.abs(p - hi) < Math.abs(PRICE_POINTS[best] - hi) ? i : best, 0)
            setMinIdx(loIdx)
            setMaxIdx(hiIdx)
          }
        }
      })
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setFetching(false))
  }, [id])

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.product_name) return toast.warning('Required', 'Product name is required')
    setLoading(true)
    try {
      const priceRange = `${formatPrice(PRICE_POINTS[minIdx])} – ${formatPrice(PRICE_POINTS[maxIdx])}${maxIdx === PRICE_POINTS.length - 1 ? '+' : ''} / mo`
      const payload = {
        ...form,
        price_range:       priceRange,
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
        <Field label="Target Industries (comma-separated)" span={2}>
          <Input value={form.target_industries} onChange={set('target_industries')} placeholder="BFSI, Healthcare, Retail" />
        </Field>
        <Field label="Description" span={2}>
          <Textarea value={form.description} onChange={set('description')} placeholder="Brief description of the product..." rows={3} />
        </Field>
        <Field label="Pain Points (comma-separated)" span={2}>
          <Textarea value={form.pain_points} onChange={set('pain_points')} placeholder="Manual hiring, slow onboarding, high attrition..." rows={2} />
        </Field>
      </div>

      {/* Price Range Slider */}
      <div style={{
        background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)',
        borderRadius: 10, padding: '16px 20px', marginTop: 4,
      }}>
        <div style={{
          fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)',
          letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 12,
        }}>Price Range (per month)</div>
        <PriceRangeSlider
          minIdx={minIdx} maxIdx={maxIdx}
          onChange={(lo, hi) => { setMinIdx(lo); setMaxIdx(hi) }}
        />
      </div>

      <FormActions onCancel={() => navigate('/products')} onSubmit={handleSubmit} loading={loading} isEdit={isEdit} />
    </FormCard>
  )
}