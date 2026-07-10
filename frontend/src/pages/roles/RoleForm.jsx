import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { rolesApi } from '../../api/roles'
import { useToast } from '../../components/layout/AppLayout'
import { FormCard, Field, Input, Textarea, Select, FormActions } from '../_shared/FormComponents'

export default function RoleForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const isEdit = Boolean(id)

  const [form, setForm] = useState({
    department: '', role: '', experience_years: '',
    skills_required: '', location: '', salary_range: '',
    rating_scale: '5', onboarding_checklist: '',
  })
  const [loading, setLoading]   = useState(false)
  const [fetching, setFetching] = useState(isEdit)

  useEffect(() => {
    if (!isEdit) return
    rolesApi.getOne(id)
      .then(data => setForm({
        ...data,
        skills_required:      (data.skills_required || []).join(', '),
        onboarding_checklist: (data.onboarding_checklist || []).join('\n'),
        experience_years:     String(data.experience_years || ''),
        rating_scale:         String(data.rating_scale || '5'),
      }))
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setFetching(false))
  }, [id])

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.role || !form.department) return toast.warning('Required', 'Role and department are required')
    setLoading(true)
    try {
      const payload = {
        department:           form.department,
        experience_years:     Number(form.experience_years) || 0,
        rating_scale:         Number(form.rating_scale) || 5,
        skills_required:      form.skills_required ? form.skills_required.split(',').map(s => s.trim()).filter(Boolean) : [],
        onboarding_checklist: form.onboarding_checklist ? form.onboarding_checklist.split('\n').map(s => s.trim()).filter(Boolean) : [],
        location:             form.location || '',
        salary_range:         form.salary_range || '',
      }
      // role is the URL key on PUT — only include it in the body on create
      if (!isEdit) payload.role = form.role

      if (isEdit) {
        await rolesApi.update(id, payload)
        toast.success('Role updated')
      } else {
        await rolesApi.create(payload)
        toast.success('Role created')
      }
      navigate('/roles')
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Loading...</div>

  return (
    <FormCard title={isEdit ? 'Edit Role' : 'Add Role'} onBack={() => navigate('/roles')}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Field label="Role Title *">
          <Input value={form.role} onChange={set('role')} placeholder="Backend Engineer" disabled={isEdit} />
        </Field>
        <Field label="Department *">
          <Input value={form.department} onChange={set('department')} placeholder="Engineering" />
        </Field>
        <Field label="Min Experience (years)">
          <Input type="number" min="0" value={form.experience_years} onChange={set('experience_years')} placeholder="3" />
        </Field>
        <Field label="Location">
          <Input value={form.location} onChange={set('location')} placeholder="Hyderabad / Remote" />
        </Field>
        <Field label="Salary Range">
          <Input value={form.salary_range} onChange={set('salary_range')} placeholder="₹8–15 LPA" />
        </Field>
        <Field label="Rating Scale">
          <Select value={form.rating_scale} onChange={set('rating_scale')}>
            {[3,4,5,10].map(n => <option key={n} value={n}>{n}</option>)}
          </Select>
        </Field>
        <Field label="Skills Required (comma-separated)" span={2}>
          <Input value={form.skills_required} onChange={set('skills_required')} placeholder="Python, FastAPI, Docker" />
        </Field>
        <Field label="Onboarding Checklist (one item per line)" span={2}>
          <Textarea value={form.onboarding_checklist} onChange={set('onboarding_checklist')} placeholder={"Set up dev environment\nMeet the team\nReview codebase"} rows={4} />
        </Field>
      </div>
      <FormActions onCancel={() => navigate('/roles')} onSubmit={handleSubmit} loading={loading} isEdit={isEdit} />
    </FormCard>
  )
}