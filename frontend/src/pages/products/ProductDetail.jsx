import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { productsApi } from '../../api/products'
import { PageLoader } from '../../components/ui/LoadingSpinner'
import { useToast } from '../../components/layout/AppLayout'
import { useRole } from '../../context/RoleContext'

export default function ProductDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { role } = useRole()
  const canManage = ['admin', 'manager', 'hr'].includes(role)

  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    productsApi.getOne(decodeURIComponent(id))
      .then(setProduct)
      .catch(err => { toast.error('Failed to load', err.message); navigate('/products') })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <PageLoader />
  if (!product) return null

  const industries = product.target_industries || []
  const painPoints = product.pain_points || []

  return (
    <div style={{ maxWidth: 780, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Back + actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button onClick={() => navigate('/products')} style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 13,
          border: '1px solid var(--color-border)', background: 'transparent',
          color: 'var(--color-text-secondary)', cursor: 'pointer',
        }}>← Back</button>
        {canManage && (
          <button onClick={() => navigate(`/products/${encodeURIComponent(product.product_name)}/edit`)} style={{
            padding: '8px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
            background: 'linear-gradient(135deg, #6366F1, #4F46E5)',
            color: '#fff', border: 'none', cursor: 'pointer',
            boxShadow: '0 0 14px rgba(99,102,241,0.25)',
          }}>Edit Product</button>
        )}
      </div>

      {/* Hero card */}
      <div style={{
        background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-xl)', padding: '28px 32px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 6 }}>
              {product.product_name}
            </h1>
            {product.category && (
              <span style={{
                padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                background: 'rgba(99,102,241,0.12)', color: '#818CF8',
                border: '1px solid rgba(99,102,241,0.2)',
              }}>{product.category}</span>
            )}
          </div>
          {product.price_range && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 2 }}>PRICE RANGE</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text-primary)' }}>{product.price_range}</div>
            </div>
          )}
        </div>

        {product.description && (
          <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--color-text-secondary)', margin: 0 }}>
            {product.description}
          </p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Target Industries */}
        <Section title="Target Industries" empty={!industries.length}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {industries.map(ind => (
              <Tag key={ind} color="#06B6D4" bg="rgba(6,182,212,0.12)" border="rgba(6,182,212,0.2)">{ind}</Tag>
            ))}
          </div>
        </Section>

        {/* Pain Points */}
        <Section title="Pain Points Addressed" empty={!painPoints.length}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {painPoints.map((pt, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{ color: '#10B981', fontSize: 13, marginTop: 1, flexShrink: 0 }}>✓</span>
                <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{pt}</span>
              </div>
            ))}
          </div>
        </Section>

      </div>
    </div>
  )
}

function Section({ title, children, empty }) {
  return (
    <div style={{
      background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-xl)', padding: '20px 24px',
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 14 }}>
        {title}
      </div>
      {empty
        ? <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Not specified</span>
        : children}
    </div>
  )
}

function Tag({ children, color, bg, border }) {
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 500,
      background: bg, color, border: `1px solid ${border}`,
    }}>{children}</span>
  )
}