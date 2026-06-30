import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { employeesApi } from '../../api/employees'
import { useToast } from '../../components/layout/AppLayout'
import { FormCard, Field, Input, Select, FormActions } from '../_shared/FormComponents'

export default function EmployeeForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const isEdit = Boolean(id)

  const [form, setForm] = useState({
    employee_id: '', employee_name: '', role: '',
    department: '', joining_date: '', manager_name: '', work_mode: 'hybrid',
  })
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEdit)

  useEffect(() => {
    if (!isEdit) return
    employeesApi.getOne(id)
      .then(data => setForm({ ...form, ...data }))
      .catch(err => toast.error('Load failed', err.message))
      .finally(() => setFetching(false))
  }, [id])

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.employee_name || !form.role) return toast.warning('Required', 'Name and role are required')
    setLoading(true)
    try {
      if (isEdit) {
        await employeesApi.update(id, form)
        toast.success('Employee updated')
      } else {
        await employeesApi.create(form)
        toast.success('Employee added')
      }
      navigate('/employees')
    } catch (err) {
      toast.error('Save failed', err.message)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Loading...</div>

  return (
    <FormCard title={isEdit ? 'Edit Employee' : 'Add Employee'} onBack={() => navigate('/employees')}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Field label="Employee ID">
          <Input value={form.employee_id} onChange={set('employee_id')} placeholder="EMP001" disabled={isEdit} />
        </Field>
        <Field label="Full Name *">
          <Input value={form.employee_name} onChange={set('employee_name')} placeholder="Alex Sharma" />
        </Field>
        <Field label="Role *">
          <Input value={form.role} onChange={set('role')} placeholder="Backend Engineer" />
        </Field>
        <Field label="Department">
          <Input value={form.department} onChange={set('department')} placeholder="Engineering" />
        </Field>
        <Field label="Joining Date">
          <Input type="date" value={form.joining_date} onChange={set('joining_date')} />
        </Field>
        <Field label="Manager Name">
          <Input value={form.manager_name} onChange={set('manager_name')} placeholder="Ravi Kumar" />
        </Field>
        <Field label="Work Mode">
          <Select value={form.work_mode} onChange={set('work_mode')}>
            <option value="hybrid">Hybrid</option>
            <option value="remote">Remote</option>
            <option value="onsite">Onsite</option>
          </Select>
        </Field>
      </div>
      <FormActions onCancel={() => navigate('/employees')} onSubmit={handleSubmit} loading={loading} isEdit={isEdit} />
    </FormCard>
  )
}