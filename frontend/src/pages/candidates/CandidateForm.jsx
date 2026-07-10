import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { candidatesApi } from '../../api/candidates'
import { useToast } from '../../components/layout/AppLayout'
import { FormCard, Field, Input, FormActions } from '../_shared/FormComponents'

export default function CandidateForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const isEdit = Boolean(id)

  const [form, setForm] = useState({
    name: '', role_applied: '', email: '', phone: '',
    experience_years: '', skills: '',
  })
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEdit)

  useEffect(() => {
    if (!isEdit) return
    candidatesApi.getOne(id)
      .then(data => setForm({
        name: data.name || '',
        role_applied: data.role_applied || '',
        email: data.email || '',
        phone: data.phone || '',
        experience_years: data.experience_years || '',
        skills: (data.skills || []).join(', '),
      }))
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setFetching(false))
  }, [id])

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.name || !form.role_applied) return toast.warning('Required', 'Name and role are required')
    setLoading(true)
    try {
      const payload = {
        name: form.name,
        role_applied: form.role_applied,
        email: form.email || '',
        phone: form.phone || '',
        experience_years: Number(form.experience_years) || 0,
        skills: form.skills ? form.skills.split(',').map(s => s.trim()).filter(Boolean) : [],
      }
      if (isEdit) {
        await candidatesApi.update(id, payload)
        toast.success('Candidate updated')
      } else {
        await candidatesApi.create(payload)
        toast.success('Candidate added')
      }
      navigate('/candidates')
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Loading...</div>

  return (
    <FormCard title={isEdit ? 'Edit Candidate' : 'Add Candidate'} onBack={() => navigate('/candidates')}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Field label="Full Name *">
          <Input value={form.name} onChange={set('name')} placeholder="Ananya Rao" />
        </Field>
        <Field label="Role Applied *">
          <Input value={form.role_applied} onChange={set('role_applied')} placeholder="Backend Engineer" />
        </Field>
        <Field label="Email">
          <Input type="email" value={form.email} onChange={set('email')} placeholder="ananya@email.com" />
        </Field>
        <Field label="Phone">
          <Input value={form.phone} onChange={set('phone')} placeholder="+91 98765 43210" />
        </Field>
        <Field label="Experience (years)">
          <Input type="number" min="0" value={form.experience_years} onChange={set('experience_years')} placeholder="4" />
        </Field>
        <Field label="Skills (comma-separated)" span={2}>
          <Input value={form.skills} onChange={set('skills')} placeholder="Python, FastAPI, Docker, PostgreSQL" />
        </Field>
      </div>
      <FormActions onCancel={() => navigate('/candidates')} onSubmit={handleSubmit} loading={loading} isEdit={isEdit} />
    </FormCard>
  )
}